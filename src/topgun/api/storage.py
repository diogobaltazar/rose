"""
Storage backend — thin wrapper around DriveClient for dependency injection.

get_storage(auth) returns a DriveClient for the authenticated user.
Raises 401 if not authenticated, 403 if Google Drive not connected.
"""

import json
from fastapi import HTTPException
from deps import get_redis
from gdrive import DriveClient, decrypt_token


def _gdrive_key(sub: str) -> str:
    return f"user:gdrive:{sub}"


def get_storage(auth: dict | None) -> DriveClient:
    if not auth:
        raise HTTPException(status_code=401, detail="Authentication required")
    sub = auth.get("sub", "")
    r = get_redis()
    encrypted = r.get(_gdrive_key(sub))
    if not encrypted:
        raise HTTPException(
            status_code=403,
            detail="Google Drive not connected. Run: topgun auth login backend",
        )
    token_data = json.loads(decrypt_token(encrypted, sub))
    return DriveClient(token_data)
