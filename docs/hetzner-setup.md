# Hetzner Server Setup for tgun.dev

## Industry Standard Approach

The standard stack for Hetzner is:

| Tool | Purpose |
|---|---|
| **Terraform** + Hetzner provider | Provision servers, firewalls, floating IPs as code |
| **cloud-init** | Configure the server on first boot (runs automatically) |
| **Ansible** | Ongoing configuration management (optional, for teams) |
| **GitHub Actions** | Deploy the application on every push to `main` |

For this project we use a provisioning script for the initial setup and GitHub Actions for deploys. Terraform is the recommended next step to make the infrastructure reproducible.

---

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
| Type | Shared CPU → Cost-Optimised → **CX22** (2 vCPU, 4 GB RAM, €4.79/mo) |
| Networking | IPv4 + IPv6 |
| SSH Key | Paste contents of `~/.ssh/tgun_deploy.pub`, name it `tgun-deploy` |
| Name | `topgun` |

Click **Create & Buy Now**. Note the IPv4 address once created.

---

## 3. Provision the Server

Run the provisioning script from your local machine. This installs Docker, configures the firewall, and enables Docker on boot:

```bash
TGUNDEV_BACKEND_IP=<your-server-ip> ./scripts/provision.sh
```

The script:
- Installs `docker.io`, `git`, `ufw`, `curl`
- Installs `docker-compose` v2.27.0 and wires it as the `docker compose` plugin
- Configures `ufw` firewall: allows SSH (22), HTTP (80), HTTPS (443), denies everything else
- Enables and starts the Docker daemon

---

## 4. Add GitHub Secrets

**Repo → Settings → Secrets and variables → Actions → New repository secret**

| Secret | Value |
|---|---|
| `DEPLOY_HOST` | Server IPv4 address |
| `DEPLOY_USER` | `root` |
| `DEPLOY_SSH_KEY` | Contents of `~/.ssh/tgun_deploy` (private key) |
| `AUTH0_DOMAIN` | Your Auth0 domain |
| `AUTH0_CLIENT_ID` | Your Auth0 client ID |
| `AUTH0_AUDIENCE` | Leave empty (or `https://tgun.dev/api` if using custom API) |

Get the private key with:

```bash
cat ~/.ssh/tgun_deploy
```
