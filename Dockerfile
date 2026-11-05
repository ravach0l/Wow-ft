# Baut Frontend und Server in ein Image. Daten liegen im Volume /data.
FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WOWFT_STATIC_DIR=/app/static \
    WOWFT_DATABASE_URL=sqlite:////data/wowft.db \
    WOWFT_COOKIE_SECURE=true
WORKDIR /app
COPY server/pyproject.toml ./
COPY server/wowft ./wowft
RUN pip install --no-cache-dir .
COPY server/alembic.ini ./
COPY server/alembic ./alembic
COPY --from=web /web/dist ./static
RUN useradd --system --uid 10001 wowft && mkdir /data && chown wowft /data
USER wowft
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')"
CMD ["python", "-m", "wowft"]
