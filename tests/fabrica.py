"""Fotos de expediente para probar las reglas sin base de datos.

Por defecto: S/ 48,000 a 45 días con orden del 3 ago 2026 (límite 17 sep),
entregado y conformado a tiempo por una persona distinta del solicitante,
con evidencia en todo. Es decir, un expediente que no debe alertar.
"""
from datetime import date
from decimal import Decimal

from conforme.reglas.modelo import ConformidadFoto, EntregableFoto, FotoExpediente, PagoFoto

SOLICITANTE, CONFORMANTE, TESORERO = 1, 2, 3


def conformidad(fecha=date(2026, 9, 18), penalidad="0.00", conformante_id=CONFORMANTE):
    return ConformidadFoto(conformante_id, "Ana Pérez Soto", fecha, Decimal(penalidad))


def entregable(numero=1, cumplido=True, n_evidencias=1):
    return EntregableFoto(numero, f"Entregable {numero}", cumplido, n_evidencias)


def pago(id=1, fecha=date(2026, 9, 30), monto="48000.00"):
    return PagoFoto(id, fecha, Decimal(monto), TESORERO)


def foto(**cambios) -> FotoExpediente:
    datos = dict(
        expediente_id=10, codigo="EXP-2026-9999", monto=Decimal("48000.00"),
        fecha_orden=date(2026, 8, 3), plazo_dias=45, fecha_entrega_real=date(2026, 9, 17),
        solicitante_id=SOLICITANTE, conformidad=conformidad(),
        entregables=(entregable(1), entregable(2)), pagos=(),
    )
    datos.update(cambios)
    return FotoExpediente(**datos)
