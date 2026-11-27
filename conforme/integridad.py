"""Monitoreo y actuaciones del OCI, sin modificar decisiones de gestión."""
from datetime import datetime, timezone

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from conforme import bitacora
from conforme.errores import ErrorValidacion
from conforme.modelos import (
    ESTADO_ABIERTA, ROL_AUDITOR, ActuacionOCI, Alerta, Bitacora,
    ConflictoInteres, Expediente, Persona, RevisionPrevia, Usuario,
)
from conforme.permisos import Actor, exigir_rol

TIPOS = ("observacion_seguimiento", "requerimiento_info", "recomendacion", "alerta_seguimiento")
ENTIDADES = {"expediente": Expediente, "revision_previa": RevisionPrevia,
             "conflicto_interes": ConflictoInteres}


def _expediente_de(sesion: Session, entidad: str, entidad_id: int) -> int:
    modelo = ENTIDADES.get(entidad)
    if modelo is None or entidad_id <= 0:
        raise ErrorValidacion("Selecciona un expediente, evaluación o conflicto válido.")
    fila = sesion.get(modelo, entidad_id)
    if fila is None:
        raise ErrorValidacion("La entidad de seguimiento no existe.")
    return fila.id if entidad == "expediente" else fila.expediente_id


def registrar_actuacion(sesion: Session, actor: Actor, *, entidad: str, entidad_id: int,
                       tipo: str, descripcion: str) -> int:
    exigir_rol(actor, ROL_AUDITOR)
    expediente_id = _expediente_de(sesion, entidad, entidad_id)
    if tipo not in TIPOS:
        raise ErrorValidacion("El tipo de actuación no es válido.")
    descripcion = (descripcion or "").strip()
    if len(descripcion) < 15 or len(descripcion) > 2000:
        raise ErrorValidacion("Describe la actuación en 15 a 2000 caracteres.")
    ahora = datetime.now(timezone.utc)
    actuacion = ActuacionOCI(entidad=entidad, entidad_id=entidad_id, tipo=tipo,
                            descripcion=descripcion, autor_id=actor.persona_id, creado_en=ahora)
    sesion.add(actuacion)
    sesion.flush()
    bitacora.registrar(sesion, ts=ahora, actor_id=actor.persona_id, accion="oci.actuacion",
                      entidad="actuacion_oci", entidad_id=actuacion.id, expediente_id=expediente_id,
                      detalle={"tipo": tipo, "entidad": entidad, "entidad_id": entidad_id,
                               "resumen": descripcion})
    if tipo == "alerta_seguimiento":
        alerta = Alerta(expediente_id=expediente_id, regla="OCI", clave=f"actuacion-{actuacion.id}",
                        severidad="media", explicacion=descripcion, datos={"actuacion_id": actuacion.id},
                        estado=ESTADO_ABIERTA, ambito="seguimiento_oci", bloqueante=False,
                        creada_en=ahora, actualizada_en=ahora)
        sesion.add(alerta)
        sesion.flush()
        bitacora.registrar(sesion, ts=ahora, actor_id=actor.persona_id,
                          accion="oci.seguimiento_abierto", entidad="alerta", entidad_id=alerta.id,
                          expediente_id=expediente_id,
                          detalle={"actuacion_id": actuacion.id, "resumen": descripcion})
    return actuacion.id


def listar_actuaciones(sesion: Session, actor: Actor, limite: int = 80) -> list[dict]:
    exigir_rol(actor, ROL_AUDITOR)
    filas = sesion.execute(select(
        ActuacionOCI.id, ActuacionOCI.entidad, ActuacionOCI.entidad_id,
        ActuacionOCI.tipo, ActuacionOCI.descripcion, ActuacionOCI.creado_en,
        Bitacora.expediente_id, Expediente.codigo.label("expediente"),
        Persona.nombres, Persona.apellidos,
    ).join(Bitacora, and_(Bitacora.entidad == "actuacion_oci",
                         Bitacora.entidad_id == ActuacionOCI.id, Bitacora.accion == "oci.actuacion"))
     .join(Expediente, Expediente.id == Bitacora.expediente_id)
     .join(Persona, Persona.id == ActuacionOCI.autor_id)
     .order_by(ActuacionOCI.id.desc()).limit(limite))
    return [{**dict(f._mapping), "autor": f"{f.nombres} {f.apellidos}"} for f in filas]


def panel(sesion: Session, actor: Actor) -> dict:
    exigir_rol(actor, ROL_AUDITOR)
    expedientes = {e.id: e for e in sesion.scalars(select(Expediente))}
    personas = {p.id: f"{p.nombres} {p.apellidos}" for p in sesion.scalars(select(Persona))}
    usuarios = {u.id: personas.get(u.persona_id, "—") for u in sesion.scalars(select(Usuario))}
    conflictos = [{"id": c.id, "expediente_id": c.expediente_id,
                   "expediente": expedientes[c.expediente_id].codigo,
                   "persona": personas.get(c.persona_id, "—"), "proveedor_ruc": c.proveedor_ruc,
                   "tipo": c.tipo, "estado": c.estado, "bloqueante": c.bloqueante,
                   "descripcion": c.descripcion}
                  for c in sesion.scalars(select(ConflictoInteres).order_by(ConflictoInteres.id.desc()))
                  if c.expediente_id in expedientes]
    revisiones = [{"id": r.id, "expediente_id": r.expediente_id,
                   "expediente": expedientes[r.expediente_id].codigo,
                   "evaluador": usuarios.get(r.evaluador_id, "—"),
                   "revisor": usuarios.get(r.revisor_independiente_id, "—"),
                   "estado": r.estado_revision_independiente or "pendiente",
                   "proveedor_ruc": r.proveedor_seleccionado_ruc,
                   "sustento": r.sustento_seleccion}
                  for r in sesion.scalars(select(RevisionPrevia).where(
                      RevisionPrevia.expediente_id.isnot(None)).order_by(RevisionPrevia.id.desc()))
                  if r.expediente_id in expedientes]
    seguimiento = [{"id": a.id, "expediente_id": a.expediente_id,
                    "expediente": expedientes[a.expediente_id].codigo,
                    "explicacion": a.explicacion, "estado": a.estado}
                   for a in sesion.scalars(select(Alerta).where(
                       Alerta.ambito == "seguimiento_oci").order_by(Alerta.id.desc()))
                   if a.expediente_id in expedientes]
    return {"expedientes": len(expedientes),
            "expedientes_disponibles": [{"id": e.id, "texto": e.codigo} for e in expedientes.values()],
            "conflictos": conflictos,
            "revisiones": revisiones, "seguimiento": seguimiento,
            "actuaciones": listar_actuaciones(sesion, actor),
            "conflictos_bloqueantes": sum(c["bloqueante"] and c["estado"] in
                                         ("en_revision", "confirmado") for c in conflictos),
            "revisiones_pendientes": sum(r["estado"] == "pendiente" for r in revisiones),
            "seguimiento_abierto": sum(a["estado"] != "cerrada" for a in seguimiento)}
