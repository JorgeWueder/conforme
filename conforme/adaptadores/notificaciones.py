"""Adaptador de notificaciones y avisos (bandeja interna hoy, correo institucional en Fase 7)."""
from typing import Protocol

from sqlalchemy.orm import Session

from conforme import config, notificaciones as _bandeja


class AdaptadorNotificaciones(Protocol):
    modo: str

    def enviar_aviso(
        self,
        sesion: Session,
        *,
        actor_id: int,
        expediente_id: int,
        rol_destino: str,
        motivo: str,
        entidad: str,
        entidad_id: int,
    ) -> None: ...


class NotificacionesBandeja:
    """Registra el aviso en la bitácora y bandeja interna sin enviar correo."""

    modo = "bandeja_simulada"

    def enviar_aviso(
        self,
        sesion: Session,
        *,
        actor_id: int,
        expediente_id: int,
        rol_destino: str,
        motivo: str,
        entidad: str,
        entidad_id: int,
    ) -> None:
        _bandeja.aviso_interno(
            sesion,
            actor_id=actor_id,
            expediente_id=expediente_id,
            rol_destino=rol_destino,
            motivo=motivo,
            entidad=entidad,
            entidad_id=entidad_id,
        )


_REGISTRO: dict[str, AdaptadorNotificaciones] = {
    "bandeja": NotificacionesBandeja(),
}


def registrar(nombre: str, adaptador: AdaptadorNotificaciones) -> None:
    _REGISTRO[nombre] = adaptador


def obtener_notificaciones() -> AdaptadorNotificaciones:
    modo = (config.leer("ADAPTADOR_NOTIFICACIONES", "bandeja") or "bandeja").strip().lower()
    return _REGISTRO.get(modo, _REGISTRO["bandeja"])
