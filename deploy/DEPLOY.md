# Deploying StockPulse AI on Railway — frontend + backend + Postgres, live

**Architecture (3 Railway resources, 1 project):**

| # | Railway resource | Source | Dockerfile |
|---|---|---|---|
| 1 | PostgreSQL | Railway → **+ New → Database → PostgreSQL** | (managed) |
| 2 | `stockpulse-backend` | GitHub repo `atifshahzad7861122-lgtm/stockpulse-ai` | `deploy/backend.Dockerfile` (build context = repo root) |
| 3 | `stockpulse-frontend` | Same GitHub repo | `deploy/frontend.Dockerfile` (build context = repo root) |

> Why Docker, not auto-detect: the repo root is a monorepo (Python backend +
> Node frontend), so Railway's Railpack cannot decide what to build
> (`Script start.sh not found` / "could not determine how to build"). Each
> service points at its explicit Dockerfile, so no auto-detection is involved.
>
> The live production frontend currently runs on **Vercel**
> (`https://stockpulse-ai-phi.vercel.app`). The Railway frontend service below
> is fully supported if you ever want everything on Railway — otherwise deploy
> only the backend + database on Railway and keep Vercel as the frontend
> (set `CORS_ALLOWED_ORIGINS` to the Vercel URL in that case).

---

## STEP 1 — Create a Railway project

1. Sign up / log in at [railway.app](https://railway.app).
2. **+ New → Empty Project**. Name it `stockpulse-ai`.

## STEP 2 — Add the PostgreSQL database

1. In the project canvas: **+ New → Database → Add PostgreSQL**.
2. Wait until it shows **Active**. Railway injects `DATABASE_URL` into the
   database service itself; other services reference it in Step 4.

## STEP 3 — Create the backend service

1. **+ New → GitHub Repo →** select `atifshahzad7861122-lgtm/stockpulse-ai`
   (root branch `main`).
2. Rename the service to `stockpulse-backend` (service → Settings → name).
3. **Settings → Build**:
   - Builder: **Dockerfile**
   - Dockerfile Path: `deploy/backend.Dockerfile`
   - (Build context stays the repository root — the Dockerfile does
     `COPY backend/requirements.txt …` / `COPY backend/ ./` relative to root.)
4. **Settings → Networking → Generate Domain** (public `*.up.railway.app` URL).
   Note it down as `BACKEND_DOMAIN`.
5. **Settings → Deploy → Healthcheck Path:** `/api/health`
   (Healthcheck Timeout: 100s is plenty for the first boot, which runs
   `init_db()` table creation.)

## STEP 4 — Backend environment variables

Service `stockpulse-backend` → **Variables** → add:

| Variable | Value | Notes |
|---|---|---|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | Reference variable pointing at the Railway Postgres service (replace `Postgres` with your DB service name). The app normalizes bare `postgresql://` URLs to the `psycopg` driver automatically. |
| `APP_ENV` | `production` | Enables the production safety check: boot **fails fast with a clear error** instead of silently running on SQLite if `DATABASE_URL` is missing. |
| `CORS_ALLOWED_ORIGINS` | `https://FRONTEND_DOMAIN` (see Step 10) | Comma-separated list is supported. Until the frontend URL exists, you may temporarily use the Vercel URL `https://stockpulse-ai-phi.vercel.app`. Never leave `*` in production without a reason. |
| `STOCKPULSE_DEV_MODE` | `false` | Keeps seeded MOCK/demo rows out of production. |
| `STOCKPULSE_SCHEDULER_ENABLED` | `false` | Recommended on Railway: the in-process collection scheduler is auxiliary; run collections on demand or via the daily GitHub workflow instead. Set `true` only if you want the 02:00 pipeline inside this service. |
| `PORT` | *(do not set)* | Railway injects it; the Dockerfile honors `$PORT` and defaults to 8000. |

Optional (safe to add later; the app boots without them):

| Variable | Purpose |
|---|---|
| `GITHUB_TOKEN` | Higher GitHub API rate limits for the trend collector |
| `RSS_FEEDS` | JSON list of `{name, url, category}` feeds |
| `OPENAI_API_KEY` / `GROQ_API_KEY`, `LLM_*` | LLM-backed agents (gracefully degrade to UNAVAILABLE when unset) |
| `LOG_LEVEL` | `INFO` default |

Never commit real values — Railway variables only.

## STEP 5 — Deploy the backend and verify

1. **Deployments → Deploy** (or push — it auto-deploys from `main`).
2. Open `https://BACKEND_DOMAIN/api/health` — expect **HTTP 200**.
   `database` reads `ok` once Postgres is reachable; it reports `degraded`
   (still HTTP 200) if the DB is unreachable instead of crashing.
3. Also check `https://BACKEND_DOMAIN/api/sources` returns a JSON list.

## STEP 6 — Create the frontend service

1. **+ New → GitHub Repo →** select the **same** repo again.
2. Rename to `stockpulse-frontend`.
3. **Settings → Build**:
   - Builder: **Dockerfile**
   - Dockerfile Path: `deploy/frontend.Dockerfile`
   - (Build context = repo root again.)
4. **Settings → Networking → Generate Domain** → note `FRONTEND_DOMAIN`.

## STEP 7 — Frontend environment variable (BEFORE first deploy)

Service `stockpulse-frontend` → **Variables** → add:

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://BACKEND_DOMAIN/api` |

> `NEXT_PUBLIC_*` values are **baked into the client JavaScript at build
> time**. Railway's Dockerfile builder auto-passes service variables as
> build args when the Dockerfile declares a matching `ARG` (ours does:
> `ARG NEXT_PUBLIC_API_URL` → `ENV` → `npm run build`). Set the variable
> **before** the first deploy; after changing it later, always **Redeploy**
> so the frontend rebuilds.

## STEP 8 — Deploy the frontend

**Deployments → Deploy.** First build takes a few minutes (`npm ci` + `next build`).

## STEP 9 — Copy the frontend public URL

From the frontend service → **Settings → Networking**, copy the public domain
(`FRONTEND_DOMAIN`).

## STEP 10 — Tighten backend CORS, redeploy backend

1. Back in `stockpulse-backend` → **Variables**:
   `CORS_ALLOWED_ORIGINS=https://FRONTEND_DOMAIN`
   (or keep the Vercel URL if Vercel stays the live frontend — comma-separate
   both if you run both).
2. **Redeploy** the backend so the new origins take effect.

## STEP 11 — End-to-end test

Open the frontend URL and verify: dashboard loads, trends/opportunities pages
fetch real data (no `Failed to fetch` cards), charts render, navigation works,
and the browser devtools show API calls going to `https://BACKEND_DOMAIN/api`
returning 200s. Then run one manual collection:
`POST https://BACKEND_DOMAIN/api/sources/{source_id}/collect` → HTTP 202.

---

## Option B — Docker Compose (any VPS / home server)

```bash
cd ~/workspace/stockpulse
docker compose -f deploy/docker-compose.yml up -d --build
```

- Frontend: `http://<server>:3000`
- Backend API: `http://<server>:8000/api`
- Postgres data persists in the `pgdata` volume.
- For a public domain, put a reverse proxy (Caddy/Nginx) in front of port 3000
  and set `CORS_ALLOWED_ORIGINS` + `NEXT_PUBLIC_API_URL` to the public URLs
  (same two variables as the Railway steps above).

---

## Minimum production environment variables (cheat sheet)

| Variable | Service | Build-time or runtime? | Purpose |
|---|---|---|---|
| `DATABASE_URL` | backend | runtime | Railway Postgres reference `${{Postgres.DATABASE_URL}}` |
| `APP_ENV` | backend | runtime | `production` (enables SQLite fail-fast guard) |
| `CORS_ALLOWED_ORIGINS` | backend | runtime | Public frontend URL(s), comma-separated |
| `STOCKPULSE_DEV_MODE` | backend | runtime | Must be `false` in production |
| `STOCKPULSE_SCHEDULER_ENABLED` | backend | runtime | `false` recommended on Railway |
| `NEXT_PUBLIC_API_URL` | frontend | **build-time** | Public backend URL + `/api` — set before first deploy, redeploy after changes |
| `PORT` | both | runtime | Injected by Railway; never hardcode |

Full variable reference: `.env.example` (placeholders only — never commit real values).

## Troubleshooting

| Symptom | Cause → fix |
|---|---|
| Railway: `Script start.sh not found` / "could not determine how to build" | Service is using Railpack auto-detect on the monorepo root. Set Builder = **Dockerfile** and Dockerfile Path = `deploy/backend.Dockerfile` (or `deploy/frontend.Dockerfile`). |
| Backend boot log: `Refusing to boot with APP_ENV=production and a SQLite DATABASE_URL` | `DATABASE_URL` variable is missing/misspelled on the backend service. Add the `${{Postgres.DATABASE_URL}}` reference. |
| Backend `/api/health` → `database: "degraded"` | Postgres unreachable — check the `DATABASE_URL` reference name matches your DB service name. |
| Frontend shows `Failed to fetch` on every panel | `NEXT_PUBLIC_API_URL` was missing/wrong when the frontend image was built. Fix the variable, then **Redeploy** (rebuild). |
| CORS errors in browser console | `CORS_ALLOWED_ORIGINS` doesn't include the exact frontend origin (scheme + host). Update + redeploy backend. |
| `sqlalchemy.exc.NoSuchModuleError: Can't load plugin: sqlalchemy.dialects:postgresql` | Bare `postgresql://` URL without driver — the app's `_normalize_database_url` (`backend/app/db/session.py`) handles this; make sure you're deployed on a build that includes that fix. |
