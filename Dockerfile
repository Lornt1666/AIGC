FROM python:3.12-slim AS dependency-builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build
COPY requirements.txt /build/requirements.txt
RUN python -m pip install --prefix=/install -r /build/requirements.txt

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000

WORKDIR /app

COPY --from=dependency-builder /install /usr/local
COPY . /app

RUN groupadd --system aigc \
    && useradd --system --gid aigc --home-dir /app --no-create-home aigc \
    && chown -R aigc:aigc /app

USER aigc

EXPOSE 8000

CMD ["sh", "-c", "exec uvicorn src.webapp.app:app --host 0.0.0.0 --port ${PORT}"]
