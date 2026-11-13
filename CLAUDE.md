# Conforme — resumen para sesiones nuevas

MVP de hackathon universitaria (entrega 25 nov 2026). Herramienta web de alerta temprana y trazabilidad para la conformidad de bienes y servicios en una entidad pública. **Alerta, no bloquea pagos ni determina responsabilidades.** Datos 100 % sintéticos.

Lee `PLAN.md` primero: tiene el plan aprobado, el estado por fase y lo pendiente.

## Stack (no cambiar sin preguntar)
Python 3.11, Streamlit multipágina (`st.navigation`), PostgreSQL con SQLAlchemy 2 + psycopg 3, migraciones SQL numeradas con ejecutor propio, Faker, pytest. Despliegue previsto: Streamlit Community Cloud + Neon (ramas dev, test, demo).

## Comandos (PowerShell, desde la raíz)
```
.\.venv\Scripts\python.exe -m scripts.migrar
.\.venv\Scripts\python.exe -m scripts.sembrar            # --reiniciar borra y recarga
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m streamlit run app.py
```
Configuración en `.env` (ver `.env.example`). `DATABASE_URL_TEST` debe ser una base dedicada: las pruebas borran su esquema.

## Arquitectura
- `app.py`: navegación por rol y banner "Datos sintéticos". Páginas en `paginas/`.
- `conforme/repositorio.py`: **única** puerta a los datos. Toda función recibe `actor` y aplica `conforme/permisos.py` en la consulta. Las páginas no usan SQLAlchemy.
- `conforme/bitacora.py`: bitácora encadenada por hash (`registrar`, `registrar_lote`, `verificar_cadena`). La línea de tiempo de un expediente es la bitácora filtrada.
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
