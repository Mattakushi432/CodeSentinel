# Webhook Setup Guide

CodeSentinel uses webhooks to receive real-time notifications when pull requests (or merge requests) are opened, updated, or reopened. This guide walks through the setup for each supported git host.

---

## Before You Start

1. **Add your repository in CodeSentinel.** Go to **Dashboard → Repositories → Add Repository**. After saving, you will see:
   - **Webhook URL** — the endpoint CodeSentinel listens on, e.g. `https://review.example.com/webhooks/3`
   - **Webhook Secret** — a randomly generated secret you will paste into your git host

2. **Ensure CodeSentinel is publicly reachable.** GitHub, GitLab.com, and Gitea Cloud need to be able to POST to your server. If you are running locally, follow [cloudflare_tunnel.md](cloudflare_tunnel.md) first.

---

## GitHub

### Step-by-step

1. Open your repository on GitHub and go to **Settings → Webhooks → Add webhook**.

2. Fill in the form:

   | Field | Value |
   |-------|-------|
   | Payload URL | Paste the **Webhook URL** from CodeSentinel, e.g. `https://review.example.com/webhooks/3` |
   | Content type | `application/json` |
   | Secret | Paste the **Webhook Secret** from CodeSentinel |
   | SSL verification | **Enable SSL verification** (requires a valid TLS cert; Caddy provisions one automatically) |

3. Under **Which events would you like to trigger this webhook?**, choose **Let me select individual events** and check only:
   - [x] **Pull requests**

   Deselect everything else to avoid noise.

4. Ensure **Active** is checked, then click **Add webhook**.

5. GitHub will send a `ping` event immediately. You will see it appear in the webhook delivery log with a green tick if CodeSentinel is reachable.

### How CodeSentinel verifies GitHub webhooks

CodeSentinel checks the `X-Hub-Signature-256` header using HMAC-SHA256 with your webhook secret. Deliveries with an invalid or missing signature are rejected with HTTP 401.

### Events handled

| GitHub event | Action | CodeSentinel behaviour |
|--------------|--------|----------------------|
| `pull_request` | `opened` | Queue a review job |
| `pull_request` | `synchronize` | Queue a review job (new commits pushed) |
| `pull_request` | `reopened` | Queue a review job |
| `pull_request` | anything else | Ignored (returns `{"status": "ignored"}`) |

---

## GitLab

### Step-by-step

1. Open your project on GitLab and go to **Settings → Webhooks → Add new webhook**.

2. Fill in the form:

   | Field | Value |
   |-------|-------|
   | URL | Paste the **Webhook URL** from CodeSentinel |
   | Secret token | Paste the **Webhook Secret** from CodeSentinel |
   | Trigger | Check **Merge request events** only |
   | SSL verification | Enable if your server has a valid TLS certificate |

   > **SSL verification note:** GitLab.com requires a valid certificate signed by a trusted CA. Self-signed certs will cause deliveries to fail. Caddy (included in the Docker Compose stack) handles this automatically with Let's Encrypt.

3. Click **Add webhook**.

4. Use the **Test → Merge request events** button to send a test payload. A green `Hook executed successfully: HTTP 200` message confirms the connection.

### How CodeSentinel verifies GitLab webhooks

CodeSentinel checks the `X-Gitlab-Token` header and compares it with your stored secret using a constant-time comparison. Deliveries with a missing or incorrect token are rejected with HTTP 401.

### Events handled

| Header `X-Gitlab-Event` | `object_attributes.action` | CodeSentinel behaviour |
|-------------------------|---------------------------|----------------------|
| `Merge Request Hook` | `open` | Queue a review job |
| `Merge Request Hook` | `update` | Queue a review job |
| `Merge Request Hook` | `reopen` | Queue a review job |
| `Merge Request Hook` | anything else | Ignored |
| Anything else | — | Ignored |

---

## Gitea

### Step-by-step

1. Open your repository on Gitea and go to **Settings → Webhooks → Add Webhook → Gitea**.

   > Use the **Gitea** type (not "Custom URL" or "Slack"). This ensures the correct `X-Gitea-Signature` header is sent.

2. Fill in the form:

   | Field | Value |
   |-------|-------|
   | Target URL | Paste the **Webhook URL** from CodeSentinel |
   | HTTP Method | POST |
   | POST Content Type | `application/json` |
   | Secret | Paste the **Webhook Secret** from CodeSentinel |
   | Trigger | **Custom Events** → check **Pull Request** only |

3. Ensure **Active** is checked, then click **Add Webhook**.

4. Scroll down to the new webhook entry and click **Test Delivery** to verify connectivity.

### How CodeSentinel verifies Gitea webhooks

Gitea uses the same HMAC-SHA256 scheme as GitHub. CodeSentinel reads the `X-Gitea-Signature` header and prepends `sha256=` before comparing. Deliveries with an invalid or missing signature are rejected with HTTP 401.

### Events handled

| Gitea action | CodeSentinel behaviour |
|--------------|----------------------|
| `opened` | Queue a review job |
| `synchronize` | Queue a review job |
| `reopened` | Queue a review job |
| anything else | Ignored |

---

## Troubleshooting

### Deliveries failing with 401

- Double-check that the secret in your git host's webhook settings exactly matches the **Webhook Secret** shown in CodeSentinel (no trailing spaces or newlines).
- Regenerating the secret in CodeSentinel requires updating the git host setting as well.

### Deliveries failing with 404

- Confirm the **Webhook URL** contains the correct numeric repository ID (visible in the CodeSentinel URL when viewing the repository).
- Confirm the repository is set to **Active** in CodeSentinel.

### Deliveries timing out

- CodeSentinel responds within milliseconds (it just queues the job). A timeout usually means the server is not reachable from the internet. Check your firewall rules or set up a [Cloudflare Tunnel](cloudflare_tunnel.md).

### Review jobs queued but no comments posted

- Check that the git host API token stored on the repository in CodeSentinel has **write** access to pull request reviews/comments.
- Check `docker compose logs app` for errors from the review worker.

### Rate limiting

CodeSentinel enforces a limit of 10 webhook deliveries per repository per 60 seconds. Deliveries beyond this limit receive HTTP 429. This protects against webhook storms from busy repositories.
