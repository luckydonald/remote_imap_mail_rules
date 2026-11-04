# syntax=docker/dockerfile:1

# The editor. The schema lives outside `frontend/`, the Vite config aliases `../schemas/rules.schema.json`.
FROM node:24-slim AS frontend
WORKDIR /build
RUN corepack enable
COPY frontend/package.json frontend/yarn.lock frontend/.yarnrc.yml frontend/
RUN cd frontend && yarn install --immutable
COPY schemas schemas
COPY frontend frontend
RUN cd frontend && yarn build

# The server, installed as an editable project: `db/migrate.py` finds `alembic.ini` and `migrations/` relative to the sources.
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src src
COPY alembic.ini ./
COPY migrations migrations
COPY schemas schemas
RUN uv sync --frozen --no-dev
COPY --from=frontend /build/frontend/dist frontend/dist

# git and ssh push the rules folder (the Git screen). No recommended packages, the image stays small.
RUN apt-get update && apt-get install -y --no-install-recommends git openssh-client && rm -rf /var/lib/apt/lists/*

# Everything the server stores lives in the volume at `/data` (database, rules, git credentials), owned by the user the server runs as.
RUN useradd --uid 10001 --no-create-home --home-dir /app app && mkdir -p /data/rules /data/git && chown -R app /data
USER app
VOLUME /data
ENV SERVER_HOST=0.0.0.0 SERVER_PORT=8000 DATA_DIR=/data DATABASE_URL=sqlite+aiosqlite:////data/db.sqlite3
EXPOSE 8000
# The watcher runs inside the server, so run exactly one container.
CMD ["python", "-m", "remote_imap_mail_rules.server.main"]
