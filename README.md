# Conforme

Expedientes, evidencias y alertas para la conformidad de servicios en la Universidad Nacional de Trujillo. **Todos los datos son sintéticos.**

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

Las cuentas de demostración son `inf1` (área usuaria), `tes1` (Tesorería) y `oci1` (OCI). La contraseña es el valor de `DEMO_PASSWORD`.

Busca la orden `OS-2026-00300` para revisar el caso de mantenimiento de laboratorio. La conformidad de la demo tiene una evidencia faltante y una penalidad estimada por revisar. El devengado figura como consulta en el SIAF y Tesorería puede registrar la referencia de un pago efectuado.

Para demostrar la corrección antes de la conformidad, abre una orden pendiente como `inf1` (por ejemplo, `OS-2026-00295`). En **Entregables**, registra qué falta en el informe de servicio. Con `tes1`, verifica que el expediente muestra la conformidad pendiente y la observación. Vuelve como `inf1`, elige **Subsanado y cumplido**, adjunta el informe corregido y describe qué verificaste. Guarda la conformidad. El OCI puede seguir la observación, la subsanación y la conformidad en la línea de tiempo y comprobar el sello. [Ruta de servicios de la UNT](https://din.unitru.edu.pe/ruta-de-procesos/) · [Reglamento de Contrataciones Públicas, art. 144](https://www.mef.gob.pe/en/por-instrumento/decreto-supremo/34044-decreto-supremo-n-009-2025-ef/file)

Si ya tienes una base cargada, ejecuta las migraciones para habilitar los campos nuevos. Carga el caso de la UNT con `scripts.sembrar` en una base de demostración vacía.

Las alertas muestran su referencia cuando corresponde. El flujo sigue la [ruta de servicios de la UNT](https://din.unitru.edu.pe/ruta-de-procesos/).

La separación de funciones y la trazabilidad sirven al control interno y a la prevención de riesgos de integridad. [Ley N.º 28716](https://cdn.www.gob.pe/uploads/document/file/2737802/Ley_N_28716.pdf.pdf) · [Modelo de Integridad Pública](https://www.gob.pe/institucion/pcm/normas-legales/7644478-002-2026-pcm-sip)

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
