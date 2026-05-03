# Cloudflare Setup for tgun.dev

## 1. DNS

In the Cloudflare dashboard for `tgun.dev` → **DNS → Records → Add record**:

| Type | Name | Content | Proxy |
|---|---|---|---|
| A | `@` | `<your-server-IP>` | Proxied (orange cloud) ✓ |
| A | `www` | `<your-server-IP>` | Proxied (orange cloud) ✓ |

---

## 2. SSL/TLS

**SSL/TLS → Overview** → set mode to **Flexible**.

With **Flexible** mode, Cloudflare handles HTTPS termination at the edge and connects to the origin over HTTP (port 80). This is the correct setting for this setup — the origin server only serves HTTP.

> **Do not use Full or Full (strict)** — those modes require the origin to serve HTTPS on port 443, which is not configured. Setting Full will result in a 521 "Web Server Is Down" error even though the server is running correctly.

---

## 3. Server Setup

The server needs Docker and Docker Compose installed. Run the provisioning script (see `docs/hetzner-setup.md`) which handles this automatically.

Ensure the web container maps to port **80** on the host. The deploy workflow writes a `compose.override.yml` on the server that handles this automatically.

---

## 4. GitHub Secrets

In the repo → **Settings → Secrets and variables → Actions → New repository secret**, add:

| Secret | Value |
|---|---|
| `DEPLOY_HOST` | Your server's IP address |
| `DEPLOY_USER` | SSH username (e.g. `root` or `ubuntu`) |
| `DEPLOY_SSH_KEY` | Contents of `~/.ssh/tgun_deploy` (private key) |
| `AUTH0_DOMAIN` | `dev-s25echrb6d3ibr8b.uk.auth0.com` |
| `AUTH0_CLIENT_ID` | Your Auth0 client ID |
| `AUTH0_AUDIENCE` | Leave empty (repo is public, no API audience needed) |

---

## 5. First Deploy

Merge `feat/160-tgundev-webapp` into `main`. The GitHub Actions workflow triggers automatically on push to `main` and:

1. SSHes into the server
2. Clones the repo (or pulls if already cloned)
3. Writes `.env` from secrets
4. Runs `docker compose up --build -d`

The webapp will be live at `https://tgun.dev`.

---

## 6. Subsequent Deploys

Every push to `main` triggers a redeploy automatically. You can also trigger manually from **Actions → Deploy to tgun.dev → Run workflow**.
