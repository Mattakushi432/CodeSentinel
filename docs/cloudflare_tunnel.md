# Exposing CodeSentinel via Cloudflare Tunnel

## Why This Is Needed

GitHub, GitLab.com, and Gitea Cloud need to send HTTP POST requests to your CodeSentinel instance whenever a pull request is opened or updated. If your server sits behind a home router, corporate firewall, or any NAT device without a public IP, those webhook deliveries will fail — the git host has no route to your machine.

Cloudflare Tunnel (`cloudflared`) solves this by creating an encrypted outbound connection from your server to Cloudflare's edge. Cloudflare proxies inbound HTTPS traffic through that tunnel to your local app — no port forwarding, no static IP, no firewall changes required.

---

## Prerequisites

- A [Cloudflare account](https://dash.cloudflare.com/sign-up) (free tier is fine)
- A domain managed by Cloudflare DNS (you can transfer an existing domain or register one through Cloudflare)
- `cloudflared` CLI installed on the server running CodeSentinel

### Install cloudflared

```bash
# Linux (Debian/Ubuntu)
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb

# macOS
brew install cloudflare/cloudflare/cloudflared

# Windows
winget install --id Cloudflare.cloudflared
```

---

## Setup: Cloudflare Tunnel (Permanent, Recommended)

### 1. Authenticate

```bash
cloudflared tunnel login
```

A browser window opens. Select your Cloudflare account and the domain you want to use. `cloudflared` saves a credentials file at `~/.cloudflared/cert.pem`.

### 2. Create the tunnel

```bash
cloudflared tunnel create codesentinel
```

This creates a tunnel with a stable UUID (e.g. `a1b2c3d4-...`) and writes a credentials JSON file to `~/.cloudflared/<UUID>.json`. Note the UUID — you will need it.

### 3. Create the tunnel configuration

Create `~/.cloudflared/config.yml`:

```yaml
tunnel: a1b2c3d4-xxxx-xxxx-xxxx-xxxxxxxxxxxx   # replace with your tunnel UUID
credentials-file: /root/.cloudflared/a1b2c3d4-xxxx-xxxx-xxxx-xxxxxxxxxxxx.json

ingress:
  - hostname: review.example.com    # replace with your domain
    service: http://localhost:8000
  - service: http_status:404
```

> If you use the Caddy container from Docker Compose, the app is exposed on port 80 (Caddy) — change `http://localhost:8000` to `http://localhost:80`. Or bypass Caddy entirely and point the tunnel directly at the FastAPI app on port 8000 (Caddy is redundant when Cloudflare handles TLS).

### 4. Route DNS to the tunnel

```bash
cloudflared tunnel route dns codesentinel review.example.com
```

This creates a CNAME record in your Cloudflare DNS zone pointing `review.example.com` to the tunnel.

### 5. Start the tunnel

```bash
cloudflared tunnel run codesentinel
```

The tunnel is now active. Test it:

```bash
curl https://review.example.com/health
# {"status": "ok", "version": "0.1.0"}
```

### 6. Update BASE_URL in .env

```dotenv
BASE_URL=https://review.example.com
```

Restart the app so it uses the new base URL when generating webhook URLs in the UI:

```bash
docker compose restart app
```

### 7. Run cloudflared as a system service (so it survives reboots)

```bash
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

---

## Docker Integration Option

If you prefer to run `cloudflared` as a fourth container alongside CodeSentinel, add the following to `docker-compose.yml`:

```yaml
  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: codesentinel_cloudflared
    restart: unless-stopped
    command: tunnel --no-autoupdate run
    environment:
      - TUNNEL_TOKEN=${CLOUDFLARE_TUNNEL_TOKEN}
    networks:
      - internal
```

Then add `CLOUDFLARE_TUNNEL_TOKEN` to your `.env`. Obtain the token from the Cloudflare Zero Trust dashboard under **Networks → Tunnels → Create a tunnel → Docker**.

The Docker approach uses a remotely-managed tunnel (configured in the Cloudflare dashboard) rather than a local `config.yml`. The ingress rule pointing to `http://app:8000` uses the Docker network service name:

```
Service: http://app:8000
```

---

## Alternative: ngrok (Development Only)

For local development where you just need to test webhook delivery quickly, [ngrok](https://ngrok.com/) is the fastest option. It does not require a domain.

```bash
# Install: https://ngrok.com/download
ngrok http 8000
```

ngrok prints a public URL like `https://abc123.ngrok.io`. Use that as your `BASE_URL` and configure it as the webhook URL in your git host.

> ngrok free tier URLs change every time you restart ngrok. You will need to update the webhook URL in your git host each time. Cloudflare Tunnel with a fixed domain is strongly preferred for anything beyond initial testing.

---

## Verifying the Setup

After completing setup, run the smoke test against your public URL:

```bash
python scripts/smoke_test.py --base-url https://review.example.com
```

Then open a test PR on your connected repository and watch `docker compose logs app` — you should see:

```
INFO  app.routers.webhooks  Queued job 1 for repo 1 PR #1
INFO  app.worker.tasks      Starting review for job 1
INFO  app.worker.tasks      Review complete for job 1
```

---

## Security Notes

- Cloudflare sits in front of your server and terminates TLS. Traffic between Cloudflare and your server travels over the encrypted tunnel — you do not need a TLS certificate on the server itself when using the tunnel without Caddy.
- CodeSentinel validates webhook signatures (HMAC-SHA256 for GitHub/Gitea, token comparison for GitLab) regardless of how the request arrives, so a compromised tunnel does not bypass application-level authentication.
- Restrict your Cloudflare tunnel's ingress to only the paths needed (`/webhooks/`, `/auth/`, etc.) if you want to limit public exposure — though the full app needs to be reachable for the UI to work across devices.
