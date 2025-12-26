## Deploy checklist (Docker Compose)

- **Prereqs**
  - **Docker**: `docker` + `docker compose` installed.
  - **Working directory**: either run commands from `deploy/`, or from repo root with `--project-directory deploy` so `deploy/.env` is used.

- **Environment**
  - **Create**: copy `deploy/example.env` to `deploy/.env` and fill in values.
  - **Must set (LLM)**:
    - `SLIDEGUARD_LLM_API_KEY`
    - `SLIDEGUARD_LLM_API_BASE`
  - **Optional**:
    - `SLIDEGUARD_LLM_MODEL` (default `/model`)
    - `SLIDEGUARD_MAX_CONCURRENCY` (default `8`)
    - `UI_HOST` (default `0.0.0.0`)
    - `UI_PORT` (default `7860`)
    - `SLIDEGUARD_REPORT_FONT_REGULAR` (absolute path to a `.ttf` file for PDF reports)
    - `SLIDEGUARD_REPORT_FONT_BOLD` (absolute path to a `.ttf` file for PDF reports)
  - **Langfuse tracing (optional)**
    - Set `SLIDEGUARD_USE_LANGFUSE=1` to enable tracing in the container.
    - Set `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`.
    - Set `LANGFUSE_HOST` (defaults to Langfuse Cloud if omitted).
    - If you see `413 Request Entity Too Large` from `opentelemetry.exporter.otlp...`, set:
      - `OTEL_EXPORTER_OTLP_COMPRESSION=gzip`
      - `OTEL_BSP_MAX_EXPORT_BATCH_SIZE=128` (or smaller)
      - Or increase your reverse proxy `client_max_body_size` in front of Langfuse.
  - **Auth DB**
    - Default is Postgres via Compose (`AUTH_DB_URL` is set automatically).
    - Override `AUTH_DB_URL` only if you want a different DB.
  - **Admin bootstrap (optional)**
    - Set `ADMIN_USERNAME`, `ADMIN_PASSWORD` to create the first user on container start.
    - Set `ADMIN_ROLE=admin` (default) or `user`.

- **Build**
  - From repo root: `docker compose --project-directory deploy -f deploy/docker-compose.yml build`
  - From `deploy/`: `docker compose -f docker-compose.yml build`
  - If you rebased / changed deps and things look stale: add `--no-cache`.

- **Run**
  - From repo root: `docker compose --project-directory deploy -f deploy/docker-compose.yml up -d`
  - From `deploy/`: `docker compose -f docker-compose.yml up -d`

- **Health / logs**
  - From repo root:
    - `docker compose --project-directory deploy -f deploy/docker-compose.yml ps`
    - `docker compose --project-directory deploy -f deploy/docker-compose.yml logs -f --tail=200 ui`
    - `docker compose --project-directory deploy -f deploy/docker-compose.yml logs -f --tail=200 db`
  - From `deploy/`:
    - `docker compose -f docker-compose.yml ps`
    - `docker compose -f docker-compose.yml logs -f --tail=200 ui`
    - `docker compose -f docker-compose.yml logs -f --tail=200 db`

- **Smoke test**
  - **Open UI**: `http://localhost:${UI_PORT:-7860}`
  - **Login**
    - If you set `ADMIN_USERNAME`/`ADMIN_PASSWORD`, log in with those.
    - Otherwise create a user inside the container:
      - From repo root: `docker compose --project-directory deploy -f deploy/docker-compose.yml exec ui poetry run slideguard admin create -u admin -r admin`
      - From `deploy/`: `docker compose -f docker-compose.yml exec ui poetry run slideguard admin create -u admin -r admin`
  - **Eval**
    - Upload a small PDF and run an evaluation (expect a result JSON and rendered slide outputs).
  - **Russian PDF reports**
    - If Russian text renders as squares in the PDF report, ensure the runtime has a Cyrillic-capable font installed (the Docker image includes DejaVu fonts).
    - If you need to force a specific font, set `SLIDEGUARD_REPORT_FONT_REGULAR` / `SLIDEGUARD_REPORT_FONT_BOLD` in `deploy/.env`.
  - **Langfuse**
    - Open your Langfuse project and confirm traces are arriving.

- **Persistence**
  - Verify named volumes exist and are attached:
    - `slideguard_cache` (evaluations/cache)
    - `file_cache` (file cache)
  - Verify auth DB persists in `db_data`.

- **Config sanity**
  - If UI fails with “LLM not available”, re-check `SLIDEGUARD_LLM_API_KEY` + `SLIDEGUARD_LLM_API_BASE` in `./.env`.
  - If UI is unreachable, confirm `UI_HOST=0.0.0.0` and port mapping matches `UI_PORT`.


