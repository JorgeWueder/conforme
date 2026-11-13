"""Alcance por rol. Se aplica dentro de las consultas del repositorio."""
from dataclasses import dataclass

from sqlalchemy import false, true

from conforme.modelos import ROL_AREA_USUARIA, ROL_AUDITOR, ROL_TESORERIA, Expediente


class PermisoDenegado(Exception):
    pass


@dataclass(frozen=True)
class Actor:
    usuario_id: int
    persona_id: int
    area_id: int
    rol: str
    nombre: str
    username: str


def filtro_expedientes(actor: Actor):
    """Condición SQL con los expedientes que el actor puede ver."""
    if actor.rol in (ROL_TESORERIA, ROL_AUDITOR):
        return true()
    if actor.rol == ROL_AREA_USUARIA:
        return Expediente.area_id == actor.area_id
    return false()


def exigir_rol(actor: Actor, *roles: str) -> None:
    if actor.rol not in roles:
        raise PermisoDenegado(f"El rol '{actor.rol}' no puede realizar esta acción.")
