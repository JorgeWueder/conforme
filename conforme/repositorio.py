"""Única puerta de lectura y escritura de la aplicación.

Toda función recibe el `actor` y aplica su alcance en la consulta. Las páginas
no usan SQLAlchemy directamente.
"""
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from conforme import bitacora
from conforme.modelos import ROL_AUDITOR, Area, Bitacora, Expediente, Persona, Proveedor
from conforme.permisos import Actor, PermisoDenegado, exigir_rol, filtro_expedientes

_NOMBRE_PERSONA = func.concat(Persona.nombres, " ", Persona.apellidos)


def _consulta_expedientes(actor: Actor):
    return (
        select(
            Expediente.id,
            Expediente.codigo,
            Expediente.tipo,
            Expediente.descripcion,
            Area.sigla.label("area_sigla"),
            Area.nombre.label("area"),
            Proveedor.razon_social.label("proveedor"),
            Proveedor.ruc.label("proveedor_ruc"),
            _NOMBRE_PERSONA.label("solicitante"),
            Expediente.solicitante_id,
            Expediente.numero_orden,
            Expediente.fecha_requerimiento,
            Expediente.fecha_orden,
            Expediente.fecha_inicio_prestacion,
            Expediente.plazo_dias,
            Expediente.fecha_entrega_real,
            Expediente.monto,
        )
        .join(Area, Area.id == Expediente.area_id)
        .join(Proveedor, Proveedor.id == Expediente.proveedor_id)
        .join(Persona, Persona.id == Expediente.solicitante_id)
        .where(filtro_expedientes(actor))
    )


def listar_expedientes(sesion: Session, actor: Actor, texto: str | None = None) -> list[dict]:
    consulta = _consulta_expedientes(actor)
    if texto and texto.strip():
        patron = f"%{texto.strip()}%"
        consulta = consulta.where(
            or_(
                Expediente.codigo.ilike(patron),
                Expediente.descripcion.ilike(patron),
                Proveedor.razon_social.ilike(patron),
            )
        )
    filas = sesion.execute(consulta.order_by(Expediente.fecha_orden.desc(), Expediente.id.desc()))
    return [dict(f._mapping) for f in filas]


def obtener_expediente(sesion: Session, actor: Actor, expediente_id: int) -> dict | None:
    """Devuelve None tanto si no existe como si está fuera del alcance del actor."""
    fila = sesion.execute(
        _consulta_expedientes(actor).where(Expediente.id == expediente_id)
    ).first()
    return dict(fila._mapping) if fila else None


def linea_de_tiempo(sesion: Session, actor: Actor, expediente_id: int) -> list[dict]:
    """Quién hizo qué, cuándo y con qué documento, en orden cronológico."""
    if obtener_expediente(sesion, actor, expediente_id) is None:
        raise PermisoDenegado("Expediente inexistente o fuera de tu alcance.")
    filas = sesion.execute(
        select(
            Bitacora.id,
            Bitacora.ts,
            Bitacora.accion,
            Bitacora.detalle,
            Bitacora.documento_sha256,
            _NOMBRE_PERSONA.label("actor"),
        )
        .outerjoin(Persona, Persona.id == Bitacora.actor_id)
        .where(Bitacora.expediente_id == expediente_id)
        .order_by(Bitacora.id)
    )
    return [dict(f._mapping) for f in filas]


def listar_bitacora(sesion: Session, actor: Actor, limite: int = 200) -> list[dict]:
    """Últimos registros de la bitácora completa. Solo auditor."""
    exigir_rol(actor, ROL_AUDITOR)
    filas = sesion.execute(
        select(
            Bitacora.id,
            Bitacora.ts,
            _NOMBRE_PERSONA.label("actor"),
            Bitacora.accion,
            Expediente.codigo.label("expediente"),
            Bitacora.documento_sha256,
            Bitacora.hash_anterior,
            Bitacora.hash,
        )
        .outerjoin(Persona, Persona.id == Bitacora.actor_id)
        .outerjoin(Expediente, Expediente.id == Bitacora.expediente_id)
        .order_by(Bitacora.id.desc())
        .limit(limite)
    )
    return [dict(f._mapping) for f in filas]


def verificar_integridad(sesion: Session, actor: Actor) -> bitacora.ResultadoVerificacion:
    """Recalcula toda la cadena de la bitácora. Solo auditor."""
    exigir_rol(actor, ROL_AUDITOR)
    return bitacora.verificar_cadena(sesion)
