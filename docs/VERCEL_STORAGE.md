# One-time Vercel storage setup (required for API keys + tables to persist)

Claycomp stores API keys and tables in **Upstash Redis** on Vercel. This is a one-time setup.

## Steps (about 2 minutes)

1. Open your Vercel project: https://vercel.com/dashboard
2. Go to **Storage** tab → **Create Database** → **Redis** (Upstash)
3. Name it (e.g. `claycomp-kv`) and click **Create**
4. Click **Connect to Project** → select **claycomp** → check all environments → **Connect**
5. **Redeploy** the project (Deployments → ⋯ → Redeploy)

Vercel automatically adds these env vars:

- `KV_REST_API_URL` (or `UPSTASH_REDIS_REST_URL`)
- `KV_REST_API_TOKEN` (or `UPSTASH_REDIS_REST_TOKEN`)

## Verify

After redeploy, open https://claycomp.vercel.app/api/health — you should see:

```json
{"ok": true, "storage": "upstash"}
```

Then open **Settings** in the app, paste your API keys once, and click **Save**. They will persist permanently on the server.

## Alternative: set env vars manually

If you already have an Upstash database:

1. Vercel project → **Settings** → **Environment Variables**
2. Add `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN` from the Upstash console
3. Redeploy
