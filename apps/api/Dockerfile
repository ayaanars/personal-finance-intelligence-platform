FROM python:3.13-slim-bookworm@sha256:ed86c82274b3c69b52fb5820f358f0bd7df0b603332063cb5c6e32bd220c3e6e
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1
WORKDIR /app
RUN pip install --no-cache-dir uv==0.12.10
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations
COPY tests ./tests
RUN uv sync --locked && useradd --create-home app && chown -R app:app /app
ENV PATH="/app/.venv/bin:$PATH"
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=4)"
CMD ["uvicorn", "ledgerx.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--reload", "--no-access-log"]
