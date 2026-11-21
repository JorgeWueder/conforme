"""Servidor de la API y de la compilación de React."""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from conforme.api import router
from conforme.errores import ErrorValidacion
from conforme.permisos import PermisoDenegado

app = FastAPI(title="Conforme")
app.include_router(router, prefix="/api")


@app.middleware("http")
async def proteger_api(request: Request, call_next):
    if not request.url.path.startswith("/api/"):
        return await call_next(request)
    # El cliente envía este encabezado en escrituras. Un formulario de otro
    # origen no puede establecerlo y la API no permite CORS.
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get("X-Conforme") != "1":
        return JSONResponse({"detail": "Solicitud no autorizada."}, status_code=403)
    respuesta = await call_next(request)
    respuesta.headers["Cache-Control"] = "no-store"
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    return respuesta


@app.exception_handler(ErrorValidacion)
async def error_validacion(_request: Request, error: ErrorValidacion):
    return JSONResponse({"detail": str(error)}, status_code=422)


@app.exception_handler(PermisoDenegado)
async def permiso_denegado(_request: Request, error: PermisoDenegado):
    return JSONResponse({"detail": str(error)}, status_code=403)


_DIST = Path(__file__).resolve().parent / "frontend" / "dist"
app.mount("/assets", StaticFiles(directory=_DIST / "assets", check_dir=False), name="assets")


@app.get("/{ruta:path}", include_in_schema=False)
def interfaz(ruta: str):
    if ruta == "api" or ruta.startswith("api/"):
        return JSONResponse({"detail": "Ruta no encontrada."}, status_code=404)
    indice = _DIST / "index.html"
    if not indice.is_file():
        return JSONResponse(
            {"detail": "Usa el servidor de Vite o compila el frontend con npm run build."},
            status_code=503,
        )
    return FileResponse(indice, headers={"Cache-Control": "no-cache"})
