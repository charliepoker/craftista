# SonarQube on Bare-Metal Raspberry Pi + Cloudflare Tunnel (GitHub-Hosted Runners)

This guide sets up **SonarQube on a dedicated Raspberry Pi host (bare-metal)** and exposes it securely to the internet via a **Cloudflare Tunnel** so **GitHub-hosted runners** can reach it (no inbound ports opened on your router).

Target hostname used in this guide:

- `sonarqube.home-lab.webdemoapp.com`

## Why this setup

- **GitHub-hosted runners need a reachable `SONAR_HOST_URL`**. A private `ClusterIP` in Kubernetes won’t work.
- **SonarQube is stateful and storage/perf sensitive**. Running it off-cluster reduces blast radius during cluster maintenance.
- **Cloudflare Tunnel** provides HTTPS access without public inbound firewall rules.

---

## Prerequisites

### Hardware / OS

- Raspberry Pi 4 (8GB recommended), or any small homelab host
- 20GB+ free disk (SSD strongly recommended; avoid SD for SonarQube data)
- Ubuntu Server 22.04 (arm64) (your setup) or another Debian-based Linux

### Accounts / DNS

- Domain managed by **Cloudflare DNS**
- Access to **Cloudflare Zero Trust** (recommended for Access policies)

### Software

- Docker + Docker Compose plugin
- `cloudflared`

---

## 1) Prepare the Raspberry Pi host

These steps should be run on the host where you will run SonarQube.

In your case, you said the SSD is mounted on **k8s-worker-1** (`10.0.0.248`) at:

- `/mnt/ssd/k8s/nfs`

If you want SonarQube data to live on that SSD path, you must run the Docker Compose stack on that same host.

### 1.1 System update

```bash
sudo apt update && sudo apt -y upgrade
```

### 1.2 Kernel parameters (required)

SonarQube requires these kernel parameters:

```bash
sudo tee /etc/sysctl.d/99-sonarqube.conf >/dev/null <<'EOF'
vm.max_map_count=524288
fs.file-max=131072
EOF

sudo sysctl --system
```

Verify:

```bash
sysctl vm.max_map_count
sysctl fs.file-max
```

### 1.3 Install Docker + Compose (if needed)

#### Ubuntu Server 22.04 (arm64) (recommended install)

On Ubuntu 22.04, installing Docker Engine from Docker's official apt repository is usually the most reliable way to get `docker compose` (Compose plugin) and Buildx.

```bash
sudo apt update
sudo apt -y install ca-certificates curl gnupg

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

sudo apt update
sudo apt -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo usermod -aG docker "$USER"
newgrp docker
```

Verify:

```bash
docker version
docker compose version
```

#### Alternative: convenience script

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"
newgrp docker
```

Verify Compose:

```bash
docker compose version
```

---

## 2) Run SonarQube + PostgreSQL with Docker Compose

### 2.1 Create working directory

```bash
mkdir -p ~/sonarqube && cd ~/sonarqube
```

### 2.2 Create `.env`

```bash
cat > .env <<'EOF'
POSTGRES_USER=sonar
POSTGRES_PASSWORD=CHANGE_ME_STRONG_PASSWORD
POSTGRES_DB=sonarqube
EOF

chmod 600 .env
```

### 2.3 Create `docker-compose.yml`

```yaml
services:
  db:
    image: postgres:15
    container_name: sonarqube-db
    restart: unless-stopped
    env_file: .env
    volumes:
      # Persist Postgres on SSD (host bind-mount)
      - /mnt/ssd/k8s/nfs/sonarqube/postgres:/var/lib/postgresql/data

  sonarqube:
    image: sonarqube:community
    container_name: sonarqube
    restart: unless-stopped
    depends_on:
      - db
    environment:
      SONAR_JDBC_URL: jdbc:postgresql://db:5432/${POSTGRES_DB}
      SONAR_JDBC_USERNAME: ${POSTGRES_USER}
      SONAR_JDBC_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      # Persist SonarQube on SSD (host bind-mounts)
      - /mnt/ssd/k8s/nfs/sonarqube/data:/opt/sonarqube/data
      - /mnt/ssd/k8s/nfs/sonarqube/extensions:/opt/sonarqube/extensions
      - /mnt/ssd/k8s/nfs/sonarqube/logs:/opt/sonarqube/logs
    ports:
      - "9000:9000"
```

Create the SSD directories on `10.0.0.248` before starting:

```bash
sudo mkdir -p \
  /mnt/ssd/k8s/nfs/sonarqube/postgres \
  /mnt/ssd/k8s/nfs/sonarqube/data \
  /mnt/ssd/k8s/nfs/sonarqube/extensions \
  /mnt/ssd/k8s/nfs/sonarqube/logs

# Make sure the current user can write (adjust to your policy)
sudo chown -R "$USER":"$USER" /mnt/ssd/k8s/nfs/sonarqube
```

### 2.4 Start services

```bash
cd ~/sonarqube
docker compose up -d
docker compose ps
```

### 2.5 Local smoke test

```bash
curl -I http://localhost:9000
```

Expected: an HTTP response (may not be 200 immediately while SonarQube initializes).

---

## 3) Install and configure Cloudflare Tunnel (`cloudflared`)

### 3.1 Install `cloudflared`

#### Ubuntu Server 22.04 (recommended: Cloudflare apt repository)

This keeps `cloudflared` up to date via `apt`.

```bash
sudo apt update

curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null

echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared jammy main' | sudo tee /etc/apt/sources.list.d/cloudflared.list

sudo apt update
sudo apt -y install cloudflared
cloudflared --version
```

#### If you're not on Ubuntu / apt repo not available

On Debian/Raspberry Pi OS, `cloudflared` is sometimes available via `apt`:

```bash
sudo apt update
sudo apt -y install cloudflared
cloudflared --version
```

If that doesn’t work on your OS version, install `cloudflared` using Cloudflare’s official package instructions for your distro.

### 3.2 Authenticate `cloudflared` (one-time)

```bash
cloudflared tunnel login
```

Follow the browser link, authenticate, and select your domain.

### 3.3 Create a tunnel

```bash
cloudflared tunnel create sonarqube
```

Note the **Tunnel UUID** from output.

### 3.4 Route DNS to the tunnel

```bash
cloudflared tunnel route dns sonarqube sonarqube.home-lab.webdemoapp.com
```

### 3.5 Create `/etc/cloudflared/config.yml`

Replace `<TUNNEL-UUID>`:

```bash
sudo mkdir -p /etc/cloudflared

sudo tee /etc/cloudflared/config.yml >/dev/null <<'EOF'
tunnel: <TUNNEL-UUID>
credentials-file: /etc/cloudflared/<TUNNEL-UUID>.json

ingress:
  - hostname: sonarqube.home-lab.webdemoapp.com
    service: http://localhost:9000
  # Optional (recommended if you enable Cloudflare Access on the UI hostname)
  - hostname: sonarqube-scan.home-lab.webdemoapp.com
    service: http://localhost:9000
  - service: http_status:404
EOF
```

Copy tunnel credentials into `/etc/cloudflared/`:

```bash
sudo cp ~/.cloudflared/<TUNNEL-UUID>.json /etc/cloudflared/
sudo chmod 600 /etc/cloudflared/<TUNNEL-UUID>.json
```

### 3.6 Run the tunnel as a service

```bash
sudo cloudflared service install
sudo systemctl enable --now cloudflared
sudo systemctl status cloudflared --no-pager
```

If `cloudflared.service` fails with `status=255/EXCEPTION`, validate config and inspect logs:

- If you see: `"cloudflared tunnel run" requires the ID or name of the tunnel to run ...`, it means your `/etc/cloudflared/config.yml` is missing the `tunnel: <TUNNEL-UUID>` line (or `cloudflared` is reading a different config).

```bash
# Validate YAML and ingress rules (prints actionable errors)
sudo cloudflared tunnel --config /etc/cloudflared/config.yml ingress validate

# Confirm the credentials JSON exists where config points
sudo ls -l /etc/cloudflared/*.json

# Read service logs
sudo journalctl -u cloudflared -n 200 --no-pager

# Run in foreground (more detailed error output)
sudo cloudflared --loglevel debug --config /etc/cloudflared/config.yml tunnel run
```

### 3.7 Verify from your laptop

Open:

- `https://sonarqube.home-lab.webdemoapp.com`

---

## 4) Secure the endpoint (recommended)

### Option A (recommended): Cloudflare Access in front of SonarQube

Use **Cloudflare Zero Trust → Access → Applications → Self-hosted**:

1. Add application for `sonarqube.home-lab.webdemoapp.com`
2. Create an allow policy (e.g., only your email / your IdP group)

**Important:** GitHub Actions scanners still need access.

If Access blocks scans: the SonarQube scanner/action typically cannot send Cloudflare Access headers, so the simplest reliable pattern is **two hostnames**:

- **UI hostname (protected by Access):** `sonarqube.home-lab.webdemoapp.com`
- **Scanner hostname (no Access, tunnel-only):** e.g. `sonarqube-scan.home-lab.webdemoapp.com`

How to add the scanner hostname:

1. Create DNS route:

   ```bash
   cloudflared tunnel route dns sonarqube sonarqube-scan.home-lab.webdemoapp.com
   ```

2. Add a second ingress rule in `/etc/cloudflared/config.yml`:

   ```yaml
   ingress:
     - hostname: sonarqube.home-lab.webdemoapp.com
       service: http://localhost:9000
     - hostname: sonarqube-scan.home-lab.webdemoapp.com
       service: http://localhost:9000
     - service: http_status:404
   ```

3. In GitHub Actions secrets set:

- `SONAR_HOST_URL` = `https://sonarqube-scan.home-lab.webdemoapp.com`

4. Keep the UI hostname protected by Access for browsers.

This still avoids opening router ports: both hostnames stay behind the tunnel.

### Option B: Expose without Access

Not recommended. If you do this, at least:

- Use a strong SonarQube admin password
- Keep SonarQube updated
- Monitor logs and audit token usage

---

## 5) First-time SonarQube setup

1. Visit `https://sonarqube.home-lab.webdemoapp.com`
2. Login: `admin` / `admin` (then change password)
3. Create projects (one per service), or let the scanner bootstrap them
4. Create a token:
   - **My Account → Security → Generate Tokens**

---

## 6) Connect GitHub Actions (GitHub-hosted runners)

In your GitHub repo settings:

- Settings → Secrets and variables → Actions → New repository secret

Add:

- `SONAR_HOST_URL` = `https://sonarqube.home-lab.webdemoapp.com` (or the scanner hostname if you enabled Cloudflare Access)
- `SONAR_TOKEN` = the token you generated

### 6.1 Set the repo secrets

In GitHub:

- **Settings → Secrets and variables → Actions → New repository secret**

Create these secrets:

- `SONAR_HOST_URL`
  - If you enabled Cloudflare Access: use `https://sonarqube-scan.home-lab.webdemoapp.com`
  - Otherwise: use `https://sonarqube.home-lab.webdemoapp.com`
- `SONAR_TOKEN`

### 6.2 Make sure project keys exist in SonarQube

This repo’s workflows use these SonarQube project keys:

- `craftista-catalogue`
- `craftista-frontend`
- `craftista-recommendation`
- `craftista-voting`

In SonarQube:

1. **Create a project** (or allow auto-provision if your token permits it)
2. Set the **Project Key** to one of the values above
3. Confirm your token has permission to analyze that project

### 6.3 GitHub Actions workflows that run SonarQube scans

Once the secrets exist, SonarQube scans run automatically on **push** to `develop`, `staging`, `main`:

- Frontend: [.github/workflows/ci-frontend.yml](.github/workflows/ci-frontend.yml)
- Recommendation: [.github/workflows/ci-recommendation.yml](.github/workflows/ci-recommendation.yml)
- Voting: [.github/workflows/ci-voting.yml](.github/workflows/ci-voting.yml)
- Catalogue: [.github/workflows/ci-catalogue.yml](.github/workflows/ci-catalogue.yml)

If `SONAR_HOST_URL` / `SONAR_TOKEN` are missing, the SonarQube scan job is skipped (so your builds still work).

---

## 7) Operations

### Backups (minimum viable)

This guide uses **bind mounts** under:

- `/mnt/ssd/k8s/nfs/sonarqube/postgres`
- `/mnt/ssd/k8s/nfs/sonarqube/data`
- `/mnt/ssd/k8s/nfs/sonarqube/extensions`
- `/mnt/ssd/k8s/nfs/sonarqube/logs`

Minimum-viable backup approach:

1. Backup PostgreSQL with `pg_dump` (preferred) or by copying the data directory while stopped.
2. Backup the SonarQube directories (`data/`, `extensions/`, `logs/`).

Example (stop briefly, then archive):

```bash
cd ~/sonarqube
docker compose down

sudo tar -C /mnt/ssd/k8s/nfs -czf ~/sonarqube-backup-$(date +%F).tgz sonarqube

docker compose up -d
```

If you need a simple backup script, say what disk/location you want to store backups (local USB disk vs NAS).

### Upgrades

1. Read SonarQube upgrade notes (major versions can require careful steps)
2. Update the image tag in `docker-compose.yml` if you pin versions
3. Run:

```bash
cd ~/sonarqube
docker compose pull
docker compose up -d
```

---

## Troubleshooting

### SonarQube is slow or fails during startup

- Prefer SSD storage
- Ensure kernel params are applied (`vm.max_map_count`)
- Check logs:

```bash
docker logs -f sonarqube
```

### Tunnel works, but you get 502/404

- Validate SonarQube is reachable locally:

```bash
curl -I http://localhost:9000
```

- Check tunnel logs:

```bash
sudo journalctl -u cloudflared -f
```

### DevOps Platform Integrations shows: "Missing permissions; permission granted on pull_requests is 'read', should be 'write'"

This means your GitHub App is installed, but it does not have sufficient **Repository permissions** for SonarQube.

Fix:

1. In GitHub, go to **Settings → Developer settings → GitHub Apps → (your app) → Permissions & events**
2. Under **Repository permissions**, set:

- **Pull requests**: **Read & write**

3. Click **Save changes**
4. Re-install / re-authorize the app:

- GitHub App → **Install App** → select the org/user → choose repositories → **Install**
- If already installed, you may need to **Configure** the installation to apply updated permissions.

5. In SonarQube, go back to **Administration → Configuration → DevOps Platform Integrations → GitHub** and click **Check configuration**

Optional (if you want Quality Gate / PR decoration later): you typically also need **Checks** (or **Commit statuses**) set to **Read & write**.

### GitHub import shows: "The redirect_uri is not associated with this application"

This is an OAuth callback URL mismatch.

Fix checklist:

1. In SonarQube, confirm **Server base URL** is set to the exact public URL you use in the browser:

- **Administration → Configuration → General → Server base URL**

2. In the GitHub App, set the **Authorization callback URL** to match the `redirect_uri` GitHub shows in the URL bar exactly:

- GitHub → **Settings → Developer settings → GitHub Apps → (your app) → OAuth credentials**

3. If you use two hostnames (UI vs scanner), make sure the hostname in SonarQube's **Server base URL** matches the one you want for interactive GitHub import.

Tip: If the URL bar contains URL-encoded text (e.g. `%3A%2F%2F`), decode it before comparing; the callback URL must match exactly.

### GitHub onboarding shows: "We couldn't load any organizations" (personal account, no org)

The GitHub onboarding/import flow in SonarQube lists **GitHub organizations**. If your repo only lives under a **personal user account** and you don’t belong to any GitHub orgs, SonarQube can’t list anything here.

Options:

- **Option A (recommended): create a free GitHub organization**, transfer the repo into it, then install the GitHub App on that org. After that, retry the import.
- **Option B: skip GitHub import entirely** and create the SonarQube project manually (or let CI auto-provision), then keep using GitHub Actions with `SONAR_HOST_URL` + `SONAR_TOKEN` (this is enough to run analyses).

---

## Next steps

- Decide whether you want **Cloudflare Access** in front of SonarQube.
- If yes, decide scanner auth method:
  - Service Token (recommended), or
  - Bypass rules
