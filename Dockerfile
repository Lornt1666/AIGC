FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

WORKDIR /app

RUN python -m pip install --upgrade pip
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/requirements.txt

RUN groupadd --system aigc \
    && useradd --system --gid aigc --create-home --home-dir /home/aigc aigc

COPY --chown=aigc:aigc . /app

EXPOSE 8000

USER aigc

CMD ["sh", "-c", "uvicorn src.webapp.app:app --host 0.0.0.0 --port ${PORT}"]
