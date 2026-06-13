Local services required for full integration testing

Overview
- Unit tests run isolated with mocks; no services needed.
- For end-to-end / integration you should run the services below.

Core services (recommended minimal set)
- redis: Used by Celery broker and LangGraph `RedisSaver` checkpointer.
- minio: S3-compatible object storage when `STORAGE_BACKEND=minio`.
- supabase (postgres + storage + realtime + rest + kong): Optional but required if using Supabase storage or DB-backed features.
- keycloak: OIDC provider used for authentication (tests mock `get_current_user`).
- chromadb: Vector DB used by HS-code embeddings (optional unless running embedding flows).

Starting the minimal set with docker-compose (from repo root):

```powershell
# From repository root
docker-compose up -d redis minio chromadb supabase-db supabase-storage supabase-realtime supabase-rest supabase-kong keycloak
```

Notes & env vars
- The repo `docker-compose.yml` already configures sensible defaults. Override with environment variables in `.env` at `apps/api/.env` or repo root.
- Typical overrides:
  - `POSTGRES_PASSWORD` (postgres/supabase)
  - `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`
  - `SUPABASE_JWT_SECRET`
  - `KEYCLOAK_ADMIN` / `KEYCLOAK_ADMIN_PASSWORD`

Quick checks
- Redis available at `redis://localhost:6379` (or `redis://redis:6379` inside Docker network).
- Minio console: http://localhost:9001, API: http://localhost:9000
- Supabase storage API: http://localhost:5000 (configured in compose)
- Keycloak admin console: http://localhost:8080

Integration test tips
- Many tests mock Supabase and Keycloak; only enable real services when running integration/e2e tests.
- If you want a minimal integration run, start `redis` and `minio` first and set `STORAGE_BACKEND=minio` in your `.env` before running the API.

Running integration tests
- Start the minimal services with the helper script from the repo root:

```powershell
.\scripts\integration-up.ps1
```

- Run only integration-marked tests:

```powershell
cd apps/api
.venv\Scripts\python.exe -m pytest -m integration -q
```

- A dedicated GitHub Actions workflow is available at `.github/workflows/integration.yml` for manual or main-branch integration runs.

- Run unit tests (fast, uses mocks):

```powershell
cd apps/api
.venv\Scripts\python.exe -m pytest tests/ -q
```

CI recommendations
- Run unit tests on every push; run integration tests in a separate CI job that brings up services (docker-compose or Testcontainers) and runs `pytest -m integration`.
- Use `pytest.ini` to declare markers (already added at `apps/api/pytest.ini`).

Next steps
- I can run a minimal `docker-compose up` for you and then run integration tests, or add a `docker-compose.integration.yml` with a trimmed service list. Which would you prefer?
