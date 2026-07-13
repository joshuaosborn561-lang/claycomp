# Supabase setup for Claycomp

Claycomp uses **Supabase Postgres** for durable storage on Vercel: tables, API keys, and auto-save.

## 1. Connect Supabase to Vercel

If you haven't already:

1. [Vercel Dashboard](https://vercel.com/dashboard) → your **claycomp** project
2. **Storage** → **Create Database** → **Supabase** → connect to project
3. Vercel adds env vars automatically:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `SUPABASE_ANON_KEY`
4. **Redeploy** the project

## 2. Run the database migration (one time)

In your [Supabase Dashboard](https://supabase.com/dashboard) → **SQL Editor**, paste and run:

`supabase/migrations/20260713000000_claycomp_schema.sql`

This creates:

- `claycomp_tables` — saved spreadsheets + enrichment columns
- `claycomp_settings` — API keys from Settings UI

## 3. Verify

Open https://claycomp.vercel.app/api/health — you should see:

```json
{"ok": true, "storage": "supabase"}
```

Then save your API keys once in **Settings**. They persist on the server permanently.

## Local development

Add to `.env`:

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

Run the same SQL migration in your Supabase project.
