"""Alcance por rol. Se aplica dentro de las consultas del repositorio.

Matriz de roles (ver README.md y PLAN.md, sección 5):
- Área usuaria: solo los expedientes de su área. Registra requerimientos, confirma la
  orden sobre la selección ya aprobada y emite conformidades. No selecciona proveedores.
- Abastecimiento (DEC): ve todos los expedientes, evalúa a los posibles proveedores,
  sustenta la selección y revisa conformidades. Nunca revisa su propia evaluación.
- Tesorería: ve todo; registra pagos. No modifica conformidades ni evaluaciones.
- OCI (auditor): ve todo en solo lectura, más la bitácora. Nunca levanta bloqueos operativos.
"""
from dataclasses import dataclass

from sqlalchemy import false, true

from conforme.modelos import (
    ROL_ABASTECIMIENTO, ROL_AREA_USUARIA, ROL_AUDITOR, ROL_TESORERIA, Expediente,
)

# Quién puede abrir la evaluación de proveedores de un expediente.
ROLES_EVALUACION_LECTURA = (ROL_ABASTECIMIENTO, ROL_TESORERIA, ROL_AUDITOR)
# Quién puede actuar en ella (evaluar, consolidar, seleccionar, revisar).
ROLES_EVALUACION_ESCRITURA = (ROL_ABASTECIMIENTO,)


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
    if actor.rol in (ROL_TESORERIA, ROL_AUDITOR, ROL_ABASTECIMIENTO):
        return true()
    if actor.rol == ROL_AREA_USUARIA:
        return Expediente.area_id == actor.area_id
    return false()


def exigir_rol(actor: Actor, *roles: str) -> None:
    if actor.rol not in roles:
        raise PermisoDenegado(f"El rol '{actor.rol}' no puede realizar esta acción.")


def exigir_otra_persona(actor: Actor, usuario_id: int | None, mensaje: str) -> None:
    """Segregación de funciones: la misma persona no puede hacer los dos pasos."""
    if usuario_id is not None and actor.usuario_id == usuario_id:
        raise PermisoDenegado(mensaje)
