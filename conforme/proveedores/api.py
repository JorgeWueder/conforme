"""Rutas HTTP de la evaluación de posibles proveedores y de la orden confirmada."""
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Path, Response
from pydantic import BaseModel, Field

from conforme.dependencias import Sesion, UsuarioActual
from conforme.proveedores import repositorio

router = APIRouter(tags=["Evaluación de proveedores"])
Id = Annotated[int, Path(gt=0, lt=2**63)]


class NuevoPostor(BaseModel):
    ruc: str = Field(max_length=11)
    razon_social: str = Field(max_length=200)
    monto_cotizado: Decimal
    plazo_dias: int
    contacto_nombre: str | None = Field(default=None, max_length=120)
    contacto_correo: str | None = Field(default=None, max_length=120)
    contacto_telefono: str | None = Field(default=None, max_length=40)
    direccion: str | None = Field(default=None, max_length=200)
    proforma_ref: str | None = Field(default=None, max_length=120)


class Analisis(BaseModel):
    postor_id: int | None = None
    dimension: Literal["antecedentes", "empresa", "personas", "colusion", "precio", "desempeno"] | None = None


class Notas(BaseModel):
    notas: str = Field(default="", max_length=2000)


class Seleccion(BaseModel):
    seleccionado_id: int
    sustento: str = Field(max_length=3000)
    descartes: dict[int, str] = {}
    declaro_sin_conflicto: bool = False


class RevisionIndependiente(BaseModel):
    aprobar: bool
    comentario: str = Field(default="", max_length=2000)


class Orden(BaseModel):
    numero_orden: str = Field(max_length=60)
    fecha_orden: date
    fecha_inicio_prestacion: date | None = None


@router.get("/evaluaciones")
def bandeja(sesion: Sesion, actor: UsuarioActual):
    return repositorio.bandeja(sesion, actor)


@router.get("/expedientes/{expediente_id}/evaluacion")
def obtener(expediente_id: Id, sesion: Sesion, actor: UsuarioActual):
    return repositorio.obtener(sesion, actor, expediente_id)


@router.post("/expedientes/{expediente_id}/postores", status_code=201)
def agregar_postor(expediente_id: Id, datos: NuevoPostor, sesion: Sesion, actor: UsuarioActual):
    return {"id": repositorio.agregar_postor(sesion, actor, expediente_id, datos.model_dump())}


@router.delete("/expedientes/{expediente_id}/postores/{postor_id}", status_code=204)
def quitar_postor(expediente_id: Id, postor_id: Id, sesion: Sesion, actor: UsuarioActual):
    repositorio.quitar_postor(sesion, actor, expediente_id, postor_id)
    return Response(status_code=204)


@router.put("/expedientes/{expediente_id}/postores/{postor_id}/notas", status_code=204)
def notas(expediente_id: Id, postor_id: Id, datos: Notas, sesion: Sesion, actor: UsuarioActual):
    repositorio.guardar_notas(sesion, actor, expediente_id, postor_id, datos.notas)
    return Response(status_code=204)


@router.post("/expedientes/{expediente_id}/evaluacion/analisis")
def analizar(expediente_id: Id, datos: Analisis, sesion: Sesion, actor: UsuarioActual):
    return repositorio.analizar(sesion, actor, expediente_id, **datos.model_dump())


@router.post("/expedientes/{expediente_id}/evaluacion/consolidado", status_code=204)
def consolidar(expediente_id: Id, sesion: Sesion, actor: UsuarioActual):
    repositorio.consolidar(sesion, actor, expediente_id)
    return Response(status_code=204)


@router.post("/expedientes/{expediente_id}/evaluacion/seleccion", status_code=204)
def seleccionar(expediente_id: Id, datos: Seleccion, sesion: Sesion, actor: UsuarioActual):
    repositorio.enviar_a_revision(sesion, actor, expediente_id, **datos.model_dump())
    return Response(status_code=204)


@router.post("/expedientes/{expediente_id}/evaluacion/revision-independiente", status_code=204)
def revision_independiente(expediente_id: Id, datos: RevisionIndependiente, sesion: Sesion, actor: UsuarioActual):
    repositorio.revisar_independiente(sesion, actor, expediente_id, **datos.model_dump())
    return Response(status_code=204)


@router.post("/expedientes/{expediente_id}/orden", status_code=204)
def confirmar_orden(expediente_id: Id, datos: Orden, sesion: Sesion, actor: UsuarioActual):
    repositorio.confirmar_orden(sesion, actor, expediente_id, **datos.model_dump())
    return Response(status_code=204)
