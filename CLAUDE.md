# Conforme — resumen para sesiones nuevas

MVP de hackathon universitaria (entrega 25 nov 2026). Herramienta web de alerta temprana y trazabilidad para la conformidad de bienes y servicios en una entidad pública. **Alerta, no bloquea pagos ni determina responsabilidades.** Datos 100 % sintéticos.

Lee `PLAN.md` primero: tiene el plan aprobado, el estado por fase y lo pendiente.

## Stack
React con Vite, API FastAPI en Python 3.11, PostgreSQL con SQLAlchemy 2 y psycopg 3, migraciones SQL numeradas, Faker y pytest. Uvicorn sirve la compilación de React y la API. Las ramas dev, test y demo pueden seguir en Neon.

## Comandos (PowerShell, desde la raíz)
```
.\.venv\Scripts\python.exe -m scripts.migrar
.\.venv\Scripts\python.exe -m scripts.sembrar            # --reiniciar borra y recarga
.\.venv\Scripts\python.exe -m scripts.medir_deteccion    # alertas vs. anomalías sembradas
.\.venv\Scripts\python.exe -m pytest -q
npm --prefix frontend ci
npm --prefix frontend run build
.\.venv\Scripts\python.exe -m uvicorn app:app --port 8501
```
Configuración en `.env` (ver `.env.example`). `DATABASE_URL_TEST` debe ser una base dedicada: las pruebas borran su esquema.

## Arquitectura
- `frontend/src/`: páginas React, navegación por rol y banner «Datos sintéticos».
- `app.py` y `conforme/api.py`: servidor, sesión firmada y rutas HTTP.
- `conforme/repositorio.py`: acceso al dominio y a los datos con `actor` y los filtros de `conforme/permisos.py`.
- `conforme/bitacora.py`: bitácora encadenada por hash (`registrar`, `registrar_lote`, `verificar_cadena`). La línea de tiempo de un expediente es la bitácora filtrada.
- `conforme/reglas/`: una función pura por regla (R1–R5), `motor.py` (evalúa y sincroniza la tabla `alerta`, idempotente) y `semaforo.py`. Parámetros normativos en `conforme/normativa.py`.
- `datos/generador.py`: datos con semilla fija, sin tocar la base. `scripts/sembrar.py` los inserta.
- `datos/caso_estrella.py`: caso de demo `EXP-2026-0300`.
- `migraciones/NNN_*.sql`: el esquema real. `conforme/modelos.py` lo refleja.

## Reglas de trabajo
- Una fase por sesión. Al terminar: pruebas, commit y actualizar `PLAN.md`.
- Cambios pequeños y dirigidos; nada que no se haya pedido.
- Lo normativo dudoso va como parámetro marcado "POR VERIFICAR" y se anota en `PLAN.md`; no se inventa.
- Nunca afirmar que algo funciona sin haberlo ejecutado.
- Código, dominio e interfaz en español. Sin secretos en el repositorio.
- La tabla `anomalia_sembrada` no puede ser leída por nada dentro de `conforme/`.
- Roles: `area_usuaria` (sus expedientes), `tesoreria` (ve todo, no edita conformidades), `auditor` (solo lectura + bitácora). Cierran o escalan alertas tesorería y auditor; nadie cierra una alerta donde figura implicado.
