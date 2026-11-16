# ==============================================================================
# Imagen única para despliegue público (Render, Koyeb, Railway, Cloud Run, VM...).
# Etapa 1 compila el frontend (Vite); etapa 2 corre FastAPI y sirve ese build en "/".
# La base NO va en la imagen: se pasa por la variable DATABASE_URL (p. ej. Aiven, con sslmode=require).
#
#   docker build -t wildfire-web .
#   docker run -p 8000:8000 -e DATABASE_URL="postgresql://usuario:clave@host:puerto/db?sslmode=require" wildfire-web
#
# Para desarrollo local con base propia sigue usándose docker-compose.yml (no usa este archivo).
# ==============================================================================
FROM node:22-alpine AS frontend
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend /app/dist ./static

ENV PYTHONUNBUFFERED=1 \
    DATA_SOURCE_MODE=database \
    CELL_MONTH_USE_CELL_ID_RANGES=true \
    PORT=8000
# Sin DATABASE_URL por defecto: debe configurarse en la plataforma (secreto), nunca en la imagen.

# Usuario sin privilegios
RUN useradd --create-home --uid 10001 app && chown -R app /app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT}/api/health" || exit 1
# La plataforma define PORT (Render/Koyeb/Cloud Run); --proxy-headers para HTTPS detrás del balanceador
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
