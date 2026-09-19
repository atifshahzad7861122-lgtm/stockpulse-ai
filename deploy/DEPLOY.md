# Deploying StockPulse AI — frontend + backend, live

Two supported paths. **Option A (Render)** is the easiest: free to start,
no server to manage. **Option B (Docker Compose)** is for any VPS / home server.

> Honest note: these files were prepared from the verified local build
> (v0.5.0, 528 backend tests passing, frontend production build passing).
> They were not image-build-tested in this environment (no Docker daemon
> here) — first deploy on Render will surface any issue, and the fix is
> usually a one-line Dockerfile tweak.

---

## Option A — Render (recommended)

### 1. Push the code to GitHub
The project is not a git repo yet, so:

```bash
cd ~/workspace/stockpulse
git init
git add -A
git commit -m "StockPulse AI v0.5.0 + deployment files"
# create an empty repo on github.com, then:
git remote add origin https://github.com/<you>/stockpulse-ai.git
git push -u origin main
```

### 2. Create the Blueprint
1. Sign up at render.com (free tier is enough to start).
2. Dashboard → **New → Blueprint** → connect your GitHub → select the repo.
3. Render reads `deploy/render.yaml` and shows 3 resources:
   `stockpulse-db` (Postgres), `stockpulse-backend` (Docker), `stockpulse-frontend` (Node).
4. Click **Apply**. First deploy takes ~5–10 minutes.

### 3. Wire the real URLs (one-time, ~2 minutes)
After the first deploy, each service gets its real public URL
(copy it from the service's dashboard page):

1. **Backend → Environment**: set `CORS_ALLOWED_ORIGINS` to the real
   frontend URL (e.g. `https://stockpulse-frontend-xxxx.onrender.com`).
2. **Frontend → Environment**: set `NEXT_PUBLIC_API_URL` to the real
   backend URL + `/api` (e.g. `https://stockpulse-backend-xxxx.onrender.com/api`).
3. **Manual Deploy → Deploy latest commit** on both services.
   (The frontend must rebuild — `NEXT_PUBLIC_*` values are baked into
   the client JavaScript at build time.)

### 4. Open the frontend URL
The dashboard loads against the **live backend** — same UI you approved,
now backed by Postgres and the real API. First boot creates all tables
automatically (`init_db`).

### Production notes
- `STOCKPULSE_DEV_MODE=false` is already set — demo/MOCK seed data stays out.
- The daily collection scheduler runs inside the backend service
  (`SCHEDULER_PIPELINE_CRON=0 2 * * *`). Free-tier services sleep when idle,
  so the 2 AM run only fires while the service is awake — acceptable for a
  personal app; a paid instance (always-on) fixes it if you ever need it.
- API keys are optional at boot: `GITHUB_TOKEN`, `RSS_FEEDS`, `OPENAI_API_KEY` /
  `GROQ_API_KEY`, `LLM_*`. Add them later under Backend → Environment when ready.
- Adobe private sync (`ADOBE_CONTRIBUTOR_SESSION`) is set via the UI/API only —
  never commit it, per the project's own rules.

---

## Option B — Docker Compose (any VPS)

```bash
cd ~/workspace/stockpulse
docker compose -f deploy/docker-compose.yml up -d --build
```

- Frontend: `http://<server>:3000`
- Backend API: `http://<server>:8000/api`
- Postgres data persists in the `pgdata` volume.
- For a public domain, put a reverse proxy (Caddy/Nginx) in front of port 3000
  and set `CORS_ALLOWED_ORIGINS` + `NEXT_PUBLIC_API_URL` to the public URLs
  (same two variables as Option A, step 3).

---

## Minimum production environment variables

| Variable | Backend/Frontend | Purpose |
|---|---|---|
| `DATABASE_URL` | backend | Postgres connection (Render injects from `stockpulse-db`) |
| `CORS_ALLOWED_ORIGINS` | backend | Public frontend URL (browser calls API cross-origin) |
| `NEXT_PUBLIC_API_URL` | frontend (build-time) | Public backend URL + `/api` |
| `STOCKPULSE_DEV_MODE` | backend | Must be `false` in production |
| `PORT` | both | Injected by the host; defaults 8000 / 3000 |

Full variable reference: `.env.example` (placeholders only — never commit real values).
