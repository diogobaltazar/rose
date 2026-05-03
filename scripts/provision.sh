#!/usr/bin/env bash
# One-time server provisioning script for tgun.dev
# Run from your local machine: ./scripts/provision.sh <server-ip>
# Or: TGUNDEV_BACKEND_IP=<ip> ./scripts/provision.sh
set -euo pipefail

TGUNDEV_BACKEND_IP="${1:-${TGUNDEV_BACKEND_IP:?Usage: $0 <server-ip>}}"
SSH="ssh -i ~/.ssh/tgun_deploy -o StrictHostKeyChecking=no root@${TGUNDEV_BACKEND_IP}"

echo "==> Provisioning ${TGUNDEV_BACKEND_IP}..."

$SSH bash <<'REMOTE'
set -euo pipefail

echo "--- Updating packages..."
apt-get update -qq

echo "--- Installing dependencies..."
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  docker.io \
  git \
  ufw \
  curl

echo "--- Installing docker-compose..."
curl -fsSL https://github.com/docker/compose/releases/download/v2.27.0/docker-compose-linux-x86_64 \
  -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
mkdir -p /usr/local/lib/docker/cli-plugins
ln -sf /usr/local/bin/docker-compose /usr/local/lib/docker/cli-plugins/docker-compose

echo "--- Configuring firewall..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "--- Enabling Docker on boot..."
systemctl enable docker
systemctl start docker

echo "--- Verifying..."
docker --version
docker compose version
ufw status

echo "==> Provisioning complete."
REMOTE

echo "==> Done. Server ${TGUNDEV_BACKEND_IP} is ready."
