# Cloudflare Setup for tgun.dev

## 1. DNS

In the Cloudflare dashboard for `tgun.dev` → **DNS → Records → Add record**:

| Type | Name | Content | Proxy |
|---|---|---|---|
| A | `@` | `<your-server-IP>` | Proxied (orange cloud) ✓ |
| A | `www` | `<your-server-IP>` | Proxied (orange cloud) ✓ |

---

## 2. SSL/TLS

**SSL/TLS → Overview** → set mode to **Full (strict)**.

Install a certificate on the server (Let's Encrypt via certbot, or use Cloudflare Origin Certificate).

---

## 3. Server Setup

The server needs Docker and Docker Compose installed. On a fresh Ubuntu/Debian VPS:

```bash
apt update && apt install -y docker.io docker-compose-plugin git
```

Ensure port **80** and **443** are open in the firewall, and that Docker's compose maps them:

```yaml
# in compose.yml, update the web service ports:
ports:
  - "80:80"
  - "443:443"
```

For now (HTTP only during setup), port 80 is sufficient — Cloudflare handles HTTPS termination at the edge when SSL mode is set to **Flexible**. Switch to **Full (strict)** once a certificate is installed on the server.

---

## 4. GitHub Secrets

In the repo → **Settings → Secrets and variables → Actions → New repository secret**, add:

| Secret | Value |
|---|---|
| `DEPLOY_HOST` | Your server's IP address |
| `DEPLOY_USER` | SSH username (e.g. `root` or `ubuntu`) |
| `DEPLOY_SSH_KEY` | Contents of `~/.ssh/id_ed25519` (private key) |
| `AUTH0_DOMAIN` | `dev-s25echrb6d3ibr8b.uk.auth0.com` |
| `AUTH0_CLIENT_ID` | Your Auth0 client ID |
| `AUTH0_AUDIENCE` | Leave empty or `https://tgun.dev/api` |
| `GH_TOKEN` | A GitHub personal access token with `repo` read scope |

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
