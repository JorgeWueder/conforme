# Conforme

Alerta temprana y trazabilidad para la conformidad de bienes y servicios. MVP de hackathon. **Todos los datos son sintéticos.**

## Puesta en marcha

Requiere Python 3.11, PostgreSQL y Node.js 20.19 o 22.12 en adelante.

1. Crear el entorno e instalar dependencias:
   ```
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```
2. Copiar `.env.example` como `.env` y completar `DATABASE_URL`, `DATABASE_URL_TEST` y `DEMO_PASSWORD`.
3. Crear el esquema y cargar los datos:
   ```
   .\.venv\Scripts\python.exe -m scripts.migrar
   .\.venv\Scripts\python.exe -m scripts.sembrar
   ```
4. Compilar React e iniciar el servidor desde la raíz:
   ```
   npm --prefix frontend ci
   npm --prefix frontend run build
   .\.venv\Scripts\python.exe -m uvicorn app:app --port 8501
   ```

Abre [Conforme en el navegador](http://localhost:8501). FastAPI sirve la compilación de React y la API desde el mismo origen.

Usuarios de demostración: `inf1` (área usuaria), `tes1` (tesorería), `oci1` (auditoría). La contraseña es el valor de `DEMO_PASSWORD`.

## Desarrollo y despliegue

En desarrollo puedes iniciar FastAPI con recarga en una terminal y Vite en otra:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app:app --reload --port 8000
npm --prefix frontend run dev
```

Vite sirve la interfaz en el puerto 8501 y reenvía `/api` al 8000. La lógica de negocio, PostgreSQL, la bitácora y las claves del proveedor de IA se manejan en el servidor.

Si el puerto de la interfaz está ocupado, elige otro con `--port` al iniciar Uvicorn o con `npm --prefix frontend run dev -- --port 8514` al usar Vite. Si cambias el puerto de la API en desarrollo, define `CONFORME_API_DEV` con su URL al iniciar Vite.

Para desplegar, compila `frontend` y sirve `app:app` con Uvicorn detrás de HTTPS. Define `SESSION_SECRET` con un valor aleatorio estable, compartido si usas varios procesos. Si configuras `BASE_URL`, debe ser la URL pública de React para que los QR apunten a `/verificar?c=…`.

## Pruebas

```
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Las pruebas con base de datos borran y recrean el esquema de `DATABASE_URL_TEST`. Usa una base dedicada.

El plan y el estado del proyecto están en `PLAN.md`.
