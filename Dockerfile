FROM python:3.13.1-slim

# uv is only used at build time to install the locked dependencies.
COPY --from=ghcr.io/astral-sh/uv:0.11.31 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8080

WORKDIR /srv

COPY pyproject.toml uv.lock .python-version README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY specs ./specs

RUN useradd --system --no-create-home appuser
USER appuser

EXPOSE 8080
CMD ["/srv/.venv/bin/python", "-m", "app"]
