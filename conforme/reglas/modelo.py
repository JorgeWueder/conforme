"""Datos que reciben y devuelven las reglas. Sin base de datos.

Una regla es una función pura: FotoExpediente -> lista de AlertaPropuesta.
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class EntregableFoto:
    numero: int
    descripcion: str
    cumplido: bool | None = None  # None = todavía sin conformidad
    n_evidencias: int = 0


@dataclass(frozen=True)
class ConformidadFoto:
    conformante_id: int
    conformante: str
    fecha_conformidad: date
    penalidad_aplicada: Decimal


@dataclass(frozen=True)
class PagoFoto:
    id: int
    fecha_pago: date
    monto: Decimal
    registrado_por: int


@dataclass(frozen=True)
class FotoExpediente:
    expediente_id: int
    codigo: str
    monto: Decimal
    fecha_orden: date
    plazo_dias: int
    fecha_entrega_real: date | None
    solicitante_id: int
    conformidad: ConformidadFoto | None = None
    entregables: tuple[EntregableFoto, ...] = ()
    pagos: tuple[PagoFoto, ...] = ()


@dataclass(frozen=True)
class AlertaPropuesta:
    regla: str
    clave: str  # distingue alertas de la misma regla en un expediente
    explicacion: str
    datos: dict = field(default_factory=dict)  # cifras usadas; solo texto y enteros
    persona_implicada_id: int | None = None


def soles(monto: Decimal) -> str:
    return f"S/ {monto:,.2f}"


def fecha(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def dias(n: int) -> str:
    return "1 día" if n == 1 else f"{n} días"
