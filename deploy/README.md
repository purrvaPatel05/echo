# Deploying ECHO to a Vultr server

One small server runs everything with Docker Compose: **Postgres + the API + the website (Caddy, automatic HTTPS)**.
Only ports 80 and 443 are open to the internet.

## 1. Create the server (Vultr dashboard)
- Cloud Compute, **Ubuntu 24.04 LTS**, **2 GB RAM** or more (the image builds need it), any region near you.
- Add your **SSH key** during creation. Note the server's **IP address**.
- Vultr firewall group (or `ufw` below): allow **22, 80, 443** only.

## 2. Install Docker (on the server, once)
```bash
ssh root@SERVER_IP
curl -fsSL https://get.docker.com | sh
ufw allow 22 && ufw allow 80 && ufw allow 443 && ufw --force enable
```

## 3. Get the code onto the server
The repo is private. Either clone it with a read-only GitHub token, or copy it from your Mac:
```bash
rsync -az --exclude .git --exclude node_modules --exclude .venv --exclude dist --exclude '.env' \
  --exclude '*.db' ./ root@SERVER_IP:/opt/echo/
```

## 4. Configure and start
```bash
cd /opt/echo/deploy
cp .env.example .env
nano .env            # set SITE_ADDRESS, POSTGRES_PASSWORD, SESSION_SECRET, DEMO_PASSWORD, ANTHROPIC_API_KEY
docker compose up -d --build
docker compose ps    # all three "running"/"healthy"
curl https://YOUR-ADDRESS/health
```
Generate secrets with `openssl rand -hex 32`. `deploy/.env` is git-ignored: it never goes to GitHub.

## Address now, domain later
- **Now:** `SITE_ADDRESS=203-0-113-7.sslip.io` (your IP with dashes). It is a real hostname, so you get real HTTPS.
- **Later:** buy the domain, add a DNS **A record** pointing at the server's IP, change `SITE_ADDRESS=echo.yourdomain.com` in
  `deploy/.env`, then `docker compose up -d`. Caddy gets the new certificate by itself. Nothing else changes.

## Keeping it healthy
- Logs: `docker compose logs -f backend` (or `web`, `postgres`).
- Update after a new push: `git pull` (or rsync again), then `docker compose up -d --build`.
- Appointment slots are generated 9 weeks ahead. The seed re-runs on every start; also add a weekly cron so slots never run out:
  `0 3 * * 1 cd /opt/echo/deploy && docker compose exec -T backend python -m app.seed`
- Back up the database: `docker compose exec -T postgres pg_dump -U echo echo > echo-$(date +%F).sql`
- Demo-grade auth: one shared password, no rate limit on the site as a whole, anyone with the address can spend Claude credits.
  Set a spending limit on the Anthropic key, and set `DEMO_ACCOUNT_LOGIN=false` if the site should not be open to everyone.
