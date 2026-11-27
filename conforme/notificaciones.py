"""Adaptador de avisos internos; registra el envío simulado en la bitácora."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from conforme import bitacora


def aviso_interno(sesion: Session, *, actor_id: int, expediente_id: int,
                 rol_destino: str, motivo: str, entidad: str, entidad_id: int) -> None:
    bitacora.registrar(
        sesion, ts=datetime.now(timezone.utc), actor_id=actor_id,
        accion="notificacion.simulada", entidad=entidad, entidad_id=entidad_id,
        expediente_id=expediente_id,
        detalle={"canal": "bandeja", "rol_destino": rol_destino, "resumen": motivo},
    )
