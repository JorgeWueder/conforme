# Imagen de despliegue: React compilado + API FastAPI en un solo contenedor.

# 1) Compila la interfaz de React.
FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 2) Servidor Python que entrega la API y la compilación.
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY app.py ./
COPY conforme/ conforme/
COPY datos/ datos/
COPY migraciones/ migraciones/
COPY scripts/ scripts/
COPY --from=frontend /frontend/dist frontend/dist
RUN useradd --create-home --uid 10001 conforme
USER conforme

# Render (y otros servicios) indican el puerto en PORT. --proxy-headers hace que la app vea
# https detrás del proxy: cookie de sesión con Secure y QR con https.
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port \"${PORT:-8000}\" --proxy-headers --forwarded-allow-ips '*'"]
