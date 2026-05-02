# Hetzner Server Setup for tgun.dev

## 1. Generate SSH Key (local machine)

```bash
ssh-keygen -t ed25519 -C "tgun.dev deploy" -f ~/.ssh/tgun_deploy -N ""
```

This creates two files:
- `~/.ssh/tgun_deploy` — private key (never share this)
- `~/.ssh/tgun_deploy.pub` — public key (paste into Hetzner)

---

## 2. Create the Server

In [console.hetzner.cloud](https://console.hetzner.cloud) → **Create Resource → Servers**:

| Setting | Value |
|---|---|
| Location | Falkenstein |
| Image | Ubuntu 24.04 |
| Type | Shared CPU → **CX22** (2 vCPU, 4 GB RAM, €4/mo) |
| Networking | IPv4 + IPv6 |
| SSH Key | Paste contents of `~/.ssh/tgun_deploy.pub`, name it `tgun-deploy` |
| Name | `tgun` |

Click **Create & Buy Now**.

---

## 3. Note the Server IP

Once created, copy the **IPv4 address** from the server detail page. You will need it for:
- Cloudflare DNS (see `cloudflare-setup.md`)
- GitHub Secret `DEPLOY_HOST`

---

## 4. Install Docker on the Server

SSH in and install Docker:

```bash
ssh -i ~/.ssh/tgun_deploy root@<server-IP>

apt update && apt install -y docker.io docker-compose-plugin git
```

Verify:

```bash
docker --version
docker compose version
```

---

## 5. Add the Private Key to GitHub Secrets

The deploy workflow SSHes into the server using the private key. Add it to GitHub:

**Repo → Settings → Secrets and variables → Actions → New repository secret**

| Secret | Value |
|---|---|
| `DEPLOY_SSH_KEY` | Contents of `~/.ssh/tgun_deploy` (the private key) |
| `DEPLOY_HOST` | Server IPv4 address |
| `DEPLOY_USER` | `root` |

Get the private key with:

```bash
cat ~/.ssh/tgun_deploy
```
