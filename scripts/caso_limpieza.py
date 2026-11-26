"""Crea el caso de demo de limpieza (OS-SIM-2026-L01) sobre una base ya sembrada.

Uso:  python -m scripts.caso_limpieza

Es un expediente del área de Servicios Generales con dos ambientes (A y B) como
entregables, sin observaciones ni conformidad: la demo recorre en vivo el ciclo
observación → comunicación → subsanación → conformidad → revisión de Abastecimiento.
Es idempotente (no repite el expediente) y no se incluye en la siembra para no alterar
sus cifras. Para empezar de cero: `python -m scripts.sembrar --reiniciar` y volver a correrlo.
Datos sintéticos.
"""
from datetime import date

from sqlalchemy import select

from conforme import auth, db, repositorio
from conforme.modelos import Expediente, Proveedor, Usuario

NUMERO_ORDEN = "OS-SIM-2026-L01"
RUC = "99900000001"


def crear(sesion) -> int | None:
    """Devuelve el id del expediente creado, o None si ya existía."""
    if sesion.scalar(select(Expediente.id).where(Expediente.numero_orden == NUMERO_ORDEN)):
        return None
    usuario = sesion.scalar(select(Usuario).where(Usuario.username == "sg1"))
    if usuario is None:
        raise SystemExit("Falta el usuario sg1: siembra la base primero (python -m scripts.sembrar).")
    actor = auth.actor_por_id(sesion, usuario.id)
    proveedor = sesion.scalar(select(Proveedor).where(Proveedor.ruc == RUC))
    if proveedor is None:
        proveedor = Proveedor(ruc=RUC, razon_social="Limpieza Integral Andina S.A.C.")
        sesion.add(proveedor)
        sesion.flush()
    return repositorio.crear_expediente(
        sesion, actor, tipo="servicio",
        descripcion="Servicio de limpieza puntual de dos ambientes administrativos de la sede central",
        proveedor_id=proveedor.id, numero_orden=NUMERO_ORDEN,
        fecha_requerimiento=date(2026, 10, 28), fecha_orden=date(2026, 11, 2),
        fecha_inicio_prestacion=date(2026, 11, 3), plazo_dias=10, monto="2400.00",
        entregables=[
            {"numero": 1, "descripcion": "Ambiente A: limpieza y desinfección, con checklist y registro fotográfico"},
            {"numero": 2, "descripcion": "Ambiente B: limpieza y desinfección, con checklist y registro fotográfico"},
        ],
    )


if __name__ == "__main__":
    with db.sesion() as s:
        nuevo = crear(s)
    print(f"Caso {NUMERO_ORDEN} creado (id {nuevo})." if nuevo else f"El caso {NUMERO_ORDEN} ya existe.")
