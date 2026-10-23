# syntax=docker/dockerfile:1
# Pin base images by digest and replace range requirements with a reviewed lockfile before production.
FROM python:3.12-slim-bookworm AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /build
COPY requirements.txt .
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt
RUN /opt/venv/bin/python -m pip check
COPY core ./core
COPY src ./src
RUN /opt/venv/bin/python -m compileall -q core src/aigc_runtime

FROM python:3.12-slim-bookworm AS runtime
ENV PATH="/opt/venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN groupadd --system --gid 10001 aigc && useradd --system --uid 10001 --gid aigc --home-dir /nonexistent --shell /usr/sbin/nologin aigc
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=10001:10001 core ./core
COPY --chown=10001:10001 scripts ./scripts
COPY --chown=10001:10001 config ./config
COPY --chown=10001:10001 src ./src
USER aigc
EXPOSE 8080
HEALTHCHECK --interval=20s --timeout=3s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health/live', timeout=2)"
CMD ["uvicorn", "core.service:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
