"""Casos de Abastecimiento y versiones inmutables de cada actuación."""
from copy import deepcopy
from datetime import datetime, timezone

from sqlalchemy import select, true
from sqlalchemy.orm import Session

from conforme import bitacora
from conforme.errores import ErrorValidacion
from conforme.modelos import ROL_ABASTECIMIENTO, RevisionPrevia, RevisionPreviaVersion
from conforme.permisos import Actor, exigir_rol
from conforme.prevencion.esquemas import Compra


class RevisionNoEncontrada(Exception):
    pass


class VersionSuperada(Exception):
    pass


def listar(sesion: Session, actor: Actor, antes_de: int | None = None) -> list[dict]:
    exigir_rol(actor, ROL_ABASTECIMIENTO)
    actual = (
        select(RevisionPreviaVersion).where(RevisionPreviaVersion.revision_id == RevisionPrevia.id)
        .order_by(RevisionPreviaVersion.numero.desc()).limit(1).lateral()
    )
    consulta = (
        select(RevisionPrevia.id, actual.c.numero, actual.c.contenido, actual.c.creado_en)
        .join(actual, true()).where(RevisionPrevia.asignado_id == actor.usuario_id)
        .order_by(RevisionPrevia.id.desc()).limit(31)
    )
    if antes_de is not None:
        consulta = consulta.where(RevisionPrevia.id < antes_de)
    return [
        dict(id=identificador, version=numero, actualizado_en=fecha,
             estado=contenido["estado"], demo=contenido["demo"],
             requerimiento=contenido["compra"]["requerimiento"], objeto=contenido["compra"]["objeto"],
             candidatos=len(contenido["compra"]["candidatos"]),
             hallazgos=len(contenido["hallazgos"]))
        for identificador, numero, contenido, fecha in sesion.execute(consulta)
    ]


def _fila(sesion: Session, actor: Actor, revision_id: int, bloquear: bool = False):
    exigir_rol(actor, ROL_ABASTECIMIENTO)
    consulta = select(RevisionPrevia.id).where(
        RevisionPrevia.id == revision_id, RevisionPrevia.asignado_id == actor.usuario_id,
    )
    if bloquear:
        consulta = consulta.with_for_update()
    if sesion.scalar(consulta) is None:
        raise RevisionNoEncontrada
    return sesion.scalars(
        select(RevisionPreviaVersion).where(RevisionPreviaVersion.revision_id == revision_id)
        .order_by(RevisionPreviaVersion.numero.desc()).limit(1)
    ).one()


def _serializar(fila: RevisionPreviaVersion) -> dict:
    return dict(id=fila.revision_id, version=fila.numero, actualizado_en=fila.creado_en, **fila.contenido)


def obtener(sesion: Session, actor: Actor, revision_id: int) -> dict:
    return _serializar(_fila(sesion, actor, revision_id))


def _escribir(sesion: Session, actor: Actor, revision_id: int, numero: int,
              contenido: dict, accion: str) -> dict:
    fila = RevisionPreviaVersion(
        revision_id=revision_id, numero=numero, contenido=contenido, creado_en=datetime.now(timezone.utc),
    )
    sesion.add(fila)
    bitacora.registrar(
        sesion, accion=f"prevencion.{accion}", actor_id=actor.persona_id,
        entidad="revision_previa", entidad_id=revision_id, detalle={"version": numero},
    )
    return _serializar(fila)


def base(compra: Compra, *, demo: bool) -> dict:
    return dict(
        estado="abierta", demo=demo, compra=compra.model_dump(mode="json"),
        fuentes=[], hallazgos=[], constancias={}, resoluciones={}, investigaciones=[], analisis={}, cierre=None,
    )


def crear(sesion: Session, actor: Actor, compra: Compra, *, demo: bool = False) -> dict:
    exigir_rol(actor, ROL_ABASTECIMIENTO)
    revision = RevisionPrevia(asignado_id=actor.usuario_id, creado_en=datetime.now(timezone.utc))
    sesion.add(revision)
    sesion.flush()
    return _escribir(sesion, actor, revision.id, 1, base(compra, demo=demo), "creada")


def base_de_cambio(sesion: Session, actor: Actor, revision_id: int,
                   version: int, *, bloquear: bool = True) -> dict:
    fila = _fila(sesion, actor, revision_id, bloquear=bloquear)
    if fila.numero != version:
        raise VersionSuperada
    if fila.contenido["estado"] == "cerrada":
        raise ErrorValidacion("La revisión está cerrada.")
    return deepcopy(fila.contenido)


def guardar(sesion: Session, actor: Actor, revision_id: int,
            version: int, contenido: dict, accion: str) -> dict:
    return _escribir(sesion, actor, revision_id, version + 1, contenido, accion)
