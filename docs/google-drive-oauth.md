# Google Drive OAuth2 Setup

One GCP project per topgun deployment — not per user. Users authenticate with their own Google accounts via your OAuth2 client.

## 1. Create a GCP project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. **Select a project** → **New Project** → name it `topgun` → **Create**

## 2. Enable the Google Drive API

1. **APIs & Services** → **Library**
2. Search `Google Drive API` → **Enable**

## 3. Configure the OAuth consent screen

1. **APIs & Services** → **OAuth consent screen**
2. User type: **External**
3. Fill in: App name `Topgun`, your user support email, your developer contact email
4. Click through Scopes without adding any
5. On **Test users**: add your own Google account
6. Save and submit

> While in Testing mode only listed test users can connect.
> The `drive.file` scope is not sensitive and does not require Google verification to publish.

## 4. Create OAuth2 credentials

1. **APIs & Services** → **Credentials** → **+ Create Credentials** → **OAuth client ID**
2. Application type: **Web application**
3. Name: `topgun-backend`
4. **Authorised redirect URIs** — add both:
   - `http://localhost:5100/api/connect/backend/callback` (local dev)
   - `https://your-domain.com/api/connect/backend/callback` (production)
5. **Create** — copy the **Client ID** and **Client Secret**

> The redirect URI is derived from `FRONTEND_URL`. It must exactly match one of the registered URIs above.
> `Error 400: redirect_uri_mismatch` means the URI you registered does not match `FRONTEND_URL + /api/connect/backend/callback`.

## 5. Configure the backend

```env
FRONTEND_URL=http://localhost:5100
BACKEND_SECRET=<generate with: python3 -c "import secrets; print(secrets.token_hex(32))">
```

`FRONTEND_URL` controls the redirect URI sent to Google during the OAuth flow.

## 6. Connect a user

**Via the webapp:** Settings → Storage Backend → CONNECT → enter Client ID and Client Secret.

**Via the CLI:**

```bash
topgun auth login
topgun config set backend gdrive \
  --client-id xxx.apps.googleusercontent.com \
  --client-secret xxxx
topgun auth login backend
```

After step 3, Google Drive is connected and the `topgun/` folder is created automatically on first write.

## Scopes used

| Scope | Purpose |
|-------|---------|
| `drive.file` | Create and write files in the topgun/ folder only |
| `drive.readonly` | Read any Drive file (needed for Obsidian vault access) |

`drive.readonly` is a sensitive scope and may require Google verification for production deployments.
For development, add test users in the OAuth consent screen.
