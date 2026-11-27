"""Servidor FastAPI de Conforme."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from conforme.api import router
from conforme.errores import ErrorValidacion
from conforme.permisos import PermisoDenegado
from conforme.prevencion import api as prevencion
from conforme.documentos import api as documentos
from conforme.proveedores import api as proveedores

app = FastAPI(title="Conforme")
app.include_router(router, prefix="/api")
app.include_router(documentos.router, prefix="/api")
app.include_router(proveedores.router, prefix="/api")
app.include_router(prevencion.router, prefix="/api")
prevencion.errores(app)


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
