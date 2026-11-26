# Next.js recibe el tráfico público y reenvía /api a FastAPI en loopback.
FROM node:22-bookworm-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOSTNAME=0.0.0.0
WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY app.py ./
COPY conforme/ conforme/
COPY datos/ datos/
COPY migraciones/ migraciones/
COPY scripts/ scripts/
COPY --from=frontend /usr/local/bin/node /usr/local/bin/node
COPY --from=frontend /frontend/.next/standalone frontend/
COPY --from=frontend /frontend/.next/static frontend/.next/static
RUN useradd --create-home --uid 10001 conforme
USER conforme
EXPOSE 8501
CMD ["bash", "scripts/servidor_contenedor.sh"]
