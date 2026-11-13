# Conforme

Alerta temprana y trazabilidad para la conformidad de bienes y servicios. MVP de hackathon. **Todos los datos son sintéticos.**

## Puesta en marcha

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
4. Abrir la aplicación:
   ```
   .\.venv\Scripts\python.exe -m streamlit run app.py
   ```

Usuarios de demostración: `inf1` (área usuaria), `tes1` (tesorería), `oci1` (auditoría). La contraseña es el valor de `DEMO_PASSWORD`.

## Pruebas

```
.\.venv\Scripts\python.exe -m pytest -q
```

Las pruebas con base de datos borran y recrean el esquema de `DATABASE_URL_TEST`; debe ser una base dedicada.

El plan y el estado del proyecto están en `PLAN.md`.
