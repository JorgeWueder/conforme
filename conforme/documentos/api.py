"""Rutas HTTP de la revisión documental y forense."""
from datetime import date
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, File, Form, Path, Response, UploadFile

from conforme.dependencias import Sesion, UsuarioActual
from conforme.documentos import repositorio
from conforme.errores import ErrorValidacion

router = APIRouter(tags=["Revisión documental"])
Id = Annotated[int, Path(gt=0, lt=2**63)]


@router.get("/documentos")
def bandeja(sesion: Sesion, actor: UsuarioActual):
    return repositorio.bandeja(sesion, actor)


@router.get("/documentos/benford")
def benford(sesion: Sesion, actor: UsuarioActual, fuente: Literal["ordenes", "pagos"] = "ordenes",
            area_id: int | None = None, ruc: str | None = None, desde: date | None = None, hasta: date | None = None):
    return repositorio.benford_transversal(sesion, actor, fuente=fuente, area_id=area_id, ruc=ruc,
                                          desde=desde, hasta=hasta)


@router.get("/documentos/archivo/{documento_id}")
def descargar(documento_id: Id, sesion: Sesion, actor: UsuarioActual):
    archivo = repositorio.descargar(sesion, actor, documento_id)
    return Response(archivo["contenido"], media_type=archivo["mime"], headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(archivo['nombre'], safe='')}"})


@router.get("/expedientes/{expediente_id}/documentos")
def obtener(expediente_id: Id, sesion: Sesion, actor: UsuarioActual):
    return repositorio.obtener(sesion, actor, expediente_id)


@router.post("/expedientes/{expediente_id}/postores/{postor_id}/documentos", status_code=201)
def subir(expediente_id: Id, postor_id: Id, sesion: Sesion, actor: UsuarioActual,
          tipo: Annotated[str, Form()], archivo: Annotated[UploadFile, File()]):
    contenido = archivo.file.read(repositorio.TAMANO_MAXIMO + 1)
    if len(contenido) > repositorio.TAMANO_MAXIMO:
        raise ErrorValidacion("El archivo supera los 5 MB.")
    return {"id": repositorio.subir_documento(sesion, actor, expediente_id, postor_id, tipo=tipo,
                                              nombre_archivo=archivo.filename, mime=archivo.content_type,
                                              contenido=contenido)}


@router.delete("/expedientes/{expediente_id}/documentos/{documento_id}", status_code=204)
def quitar(expediente_id: Id, documento_id: Id, sesion: Sesion, actor: UsuarioActual):
    repositorio.quitar_documento(sesion, actor, expediente_id, documento_id)
    return Response(status_code=204)


@router.post("/expedientes/{expediente_id}/documentos/analisis")
def analizar(expediente_id: Id, sesion: Sesion, actor: UsuarioActual):
    return repositorio.analizar(sesion, actor, expediente_id)
