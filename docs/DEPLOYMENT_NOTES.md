# Deployment Notes

**Status: Docker + CI are done and verified. Render deployment is deliberately deferred** — this
doc is the checklist for when that happens, not a record of it having happened. Nothing here has
been executed against a real Render account yet.

## Docker

### Image
Multi-stage build (`Dockerfile`) — a `builder` stage installs Python deps, the runtime stage copies
only the installed packages + `src/`, not build tools or caches.

- **Base:** `python:3.11-slim`
- **Size:** 474MB. History: dropped from an initial 737MB to 471MB after removing `spacy` and
  `langchain-groq` pins that were never actually imported anywhere, then rose slightly to 474MB once
  `langchain-groq` was deliberately re-added, now genuinely used by the AI Reasoner and AI Critic
  agents. Verified by a full rebuild + container run against `/health` and a live `/analyze` call
  (with a real `GROQ_API_KEY`) confirming both `ai_opinion` and `ai_critique` populate correctly
  inside the container, not just in local dev.
- **Healthcheck:** built in (`HEALTHCHECK` instruction), polls `/health` every 30s
- **Exposed port:** 8000

### Build & run locally
```bash
docker build -t diagnosis-ai:latest .
docker run -p 8000:8000 --env-file .env diagnosis-ai:latest
```

### Full stack via docker-compose
```bash
docker compose up --build
```
Runs the backend container plus a **dev-mode** frontend (`node:20-alpine`, `npm run dev`) — this is
for local full-stack testing, not a production frontend deployment (see below).

### Environment variables (backend)
| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/database.db` | SQLite file path — see the persistence warning below for Render |
| `ENVIRONMENT` | `development` | `test` forces in-memory SQLite (used by the test suite / CI) |
| `LOG_LEVEL` | `INFO` | |
| `ALLOWED_ORIGINS` | `http://localhost:5173,http://localhost:3000` | CORS — **must be updated** to the real frontend URL once deployed |
| `GROQ_API_KEY` | — | **Used by the AI Reasoning Agent and the AI Critic Agent** (one shared client, two agents). Without it, `/analyze` still works fully — `ai_opinion` and `ai_critique` are simply `null` on every response. Get a free key at console.groq.com. |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Which Groq model both LLM agents call |
| `OLLAMA_*` | — | Defined but still unused — no agent currently falls back to Ollama |

### Environment variables (frontend)
| Variable | Default | Notes |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | **Must be updated** to the deployed backend URL |
| `VITE_APP_NAME` | `Diagnosis Reasoning Engine` | |

## CI/CD (`.github/workflows/deploy.yml`)

Runs on every push/PR to `main`:
1. **`backend-tests`** — `pytest -v` against an in-memory SQLite DB
2. **`frontend-build`** — `npm ci && npm run build`
3. **`docker-build`** — builds the image, runs the container, polls `/health` until it responds
4. **`deploy`** — *no-ops intentionally* until Render is configured. It checks for a
   `RENDER_DEPLOY_HOOK_URL` repository secret; if unset, it logs a message and exits cleanly rather
   than failing every run. Once a Render web service exists, adding its Deploy Hook URL as that
   secret is the **only** change needed to make deploys start firing automatically on push to `main`.

## Render deployment checklist (when ready)

Not done yet — this is the plan, written down so it's a checklist rather than something to
figure out from scratch later.

1. **Create a Render account**, connect the GitHub repo.
2. **Backend — Web Service:**
   - Environment: Docker (points at the repo's `Dockerfile`)
   - Set the environment variables from the table above — critically `ALLOWED_ORIGINS` to the
     frontend's real Render URL once known, and `DATABASE_URL` (see persistence note below)
   - Health check path: `/health`
3. **⚠️ SQLite persistence:** Render's web service filesystem is **ephemeral** — it resets on every
   deploy and on restarts. As shipped, `patient_records` (history, analytics, feedback) would be
   **wiped on every deploy** unless a [Render Disk](https://render.com/docs/disks) is attached and
   mounted at the path `DATABASE_URL` points to (`/app/data` by default). This is a real
   consideration to decide on before going live, not an oversight to fix later — either attach a
   disk, or accept that history resets on redeploy for a demo instance.
4. **Frontend — Static Site** (not the dev-mode docker-compose service): build command `npm run
   build` in `frontend/`, publish directory `frontend/dist`. Set `VITE_API_URL` to the backend's
   Render URL at build time (Vite bakes env vars in at build, not runtime).
5. **Wire up CI/CD:** create a Deploy Hook on the Render backend service, add it as the
   `RENDER_DEPLOY_HOOK_URL` secret in the GitHub repo settings. The existing `deploy` job in
   `deploy.yml` picks it up automatically — no workflow changes needed.
6. **Verify:** `/health` on the live URL, a full `/analyze` call through the live UI, and a handful
   of the real-data validation cases re-run against the live instance.

## Known gaps to revisit

- `langchain`/`langchain-community` remain in `requirements.txt` even though no direct import of
  either exists in `src/` (only `langgraph` is imported) — unlike `spacy`/`langchain-groq`, these
  weren't confirmed safe to remove (langgraph's own dependency chain wasn't fully audited), so they
  were left in place rather than risk a break. Worth a closer look before removing.
- No production frontend Docker image — `docker-compose.yml`'s frontend service is dev-mode only
  (`npm run dev`), fine for local full-stack testing, not what Render's static-site deploy would use.
