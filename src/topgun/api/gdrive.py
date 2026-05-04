"""
Google Drive storage backend.

Reads/writes user data files in the user's topgun/ folder on Google Drive:
  registry.jsonl, timers.jsonl, config.json, credentials.enc, vault/

Authentication: per-user refresh token stored encrypted in Redis.
Encryption key = HMAC(BACKEND_SECRET, auth0_sub)
"""

import base64
import hashlib
import hmac
import secrets
import io
import json
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

GDRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive.file",      # write files created by app
    "https://www.googleapis.com/auth/drive.readonly",  # read any file in Drive
]
BACKEND_SECRET = os.environ.get("BACKEND_SECRET", "dev-secret-change-in-prod")
TOPGUN_FOLDER = "topgun"


# ── Encryption ────────────────────────────────────────────────────────────────

def _derive_key(auth0_sub: str) -> bytes:
    return hmac.new(
        BACKEND_SECRET.encode(),
        auth0_sub.encode(),
        hashlib.sha256,
    ).digest()


def encrypt_token(token: str, auth0_sub: str) -> str:
    key = _derive_key(auth0_sub)
    token_bytes = token.encode()
    key_stream = (key * (len(token_bytes) // len(key) + 1))[: len(token_bytes)]
    return bytes(a ^ b for a, b in zip(token_bytes, key_stream)).hex()


def decrypt_token(encrypted_hex: str, auth0_sub: str) -> str:
    key = _derive_key(auth0_sub)
    encrypted = bytes.fromhex(encrypted_hex)
    key_stream = (key * (len(encrypted) // len(key) + 1))[: len(encrypted)]
    return bytes(a ^ b for a, b in zip(encrypted, key_stream)).decode()


# ── OAuth helpers ─────────────────────────────────────────────────────────────

def _flow(client_id: str, client_secret: str, redirect_uri: str):
    from google_auth_oauthlib.flow import Flow
    return Flow.from_client_config(
        {"web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
        }},
        scopes=GDRIVE_SCOPES,
        redirect_uri=redirect_uri,
    )


def _pkce_pair() -> tuple[str, str]:
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return code_verifier, code_challenge


def get_auth_url(state: str, *, client_id: str, client_secret: str, redirect_uri: str) -> tuple[str, str]:
    """Returns (auth_url, code_verifier)."""
    code_verifier, code_challenge = _pkce_pair()
    flow = _flow(client_id, client_secret, redirect_uri)
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
        code_challenge=code_challenge,
        code_challenge_method="S256",
    )
    return auth_url, code_verifier


def exchange_code(code: str, *, client_id: str, client_secret: str, redirect_uri: str, code_verifier: str) -> dict:
    flow = _flow(client_id, client_secret, redirect_uri)
    flow.fetch_token(code=code, code_verifier=code_verifier)
    creds = flow.credentials
    return {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": client_id,
        "client_secret": client_secret,
    }


# ── Drive client ──────────────────────────────────────────────────────────────

class DriveClient:
    """Google Drive client for a single user. All paths relative to topgun/."""

    def __init__(self, token_data: dict):
        creds = Credentials(
            token=token_data.get("access_token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=token_data.get("client_id", ""),
            client_secret=token_data.get("client_secret", ""),
            scopes=GDRIVE_SCOPES,
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        self._svc = build("drive", "v3", credentials=creds, cache_discovery=False)
        self._folder_id: str | None = None

    def _folder(self) -> str:
        if self._folder_id:
            return self._folder_id
        results = self._svc.files().list(
            q=f"name='{TOPGUN_FOLDER}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
            spaces="drive", fields="files(id)",
        ).execute()
        files = results.get("files", [])
        if files:
            self._folder_id = files[0]["id"]
            return self._folder_id
        folder = self._svc.files().create(
            body={"name": TOPGUN_FOLDER, "mimeType": "application/vnd.google-apps.folder"},
            fields="id",
        ).execute()
        self._folder_id = folder["id"]
        return self._folder_id

    def _file_id(self, filename: str) -> str | None:
        folder_id = self._folder()
        results = self._svc.files().list(
            q=f"name='{filename}' and '{folder_id}' in parents and trashed=false",
            spaces="drive", fields="files(id)",
        ).execute()
        files = results.get("files", [])
        return files[0]["id"] if files else None

    def read_text(self, filename: str) -> str:
        file_id = self._file_id(filename)
        if not file_id:
            return ""
        return self._read_by_id(file_id)

    def _read_by_id(self, file_id: str) -> str:
        # Check MIME type — Google Docs need export(), others use get_media()
        meta = self._svc.files().get(fileId=file_id, fields="mimeType").execute()
        mime = meta.get("mimeType", "")
        buf = io.BytesIO()
        if mime == "application/vnd.google-apps.document":
            request = self._svc.files().export_media(fileId=file_id, mimeType="text/plain")
        else:
            request = self._svc.files().get_media(fileId=file_id)
        dl = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = dl.next_chunk()
        return buf.getvalue().decode("utf-8", errors="replace")

    def write_text(self, filename: str, content: str) -> None:
        folder_id = self._folder()
        file_id = self._file_id(filename)
        media = MediaIoBaseUpload(io.BytesIO(content.encode("utf-8")), mimetype="text/plain")
        if file_id:
            self._svc.files().update(fileId=file_id, media_body=media).execute()
        else:
            self._svc.files().create(
                body={"name": filename, "parents": [folder_id]},
                media_body=media, fields="id",
            ).execute()

    def append_jsonl(self, filename: str, record: dict) -> None:
        existing = self.read_text(filename).rstrip("\n")
        line = json.dumps(record, separators=(",", ":"))
        updated = f"{existing}\n{line}\n" if existing else f"{line}\n"
        self.write_text(filename, updated)

    def read_jsonl(self, filename: str) -> list[dict]:
        records = []
        for line in self.read_text(filename).splitlines():
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return records

    def rewrite_jsonl(self, filename: str, records: list[dict]) -> None:
        content = "\n".join(json.dumps(r, separators=(",", ":")) for r in records)
        self.write_text(filename, content + "\n" if content else "")

    def read_json(self, filename: str) -> dict:
        content = self.read_text(filename)
        if not content.strip():
            return {}
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {}

    def write_json(self, filename: str, data: dict) -> None:
        self.write_text(filename, json.dumps(data, indent=2, ensure_ascii=False))
