"""Caso estrella de la demo, hecho a mano.

Servicio de S/ 48,000 a 45 días, entregado 12 días tarde.
Fecha límite = 3 ago + 45 días = 17 sep 2026; entrega real = 29 sep 2026.

F1: solo la cabecera del expediente.
F2 (pendiente): un entregable sin evidencia, penalidad no aplicada y la misma
persona como solicitante y conformante.
"""
from datetime import date
from decimal import Decimal

CODIGO = "EXP-2026-0300"
AREA_SIGLA = "INF"
USERNAME_SOLICITANTE = "inf1"

EXPEDIENTE = {
    "codigo": CODIGO,
    "tipo": "servicio",
    "descripcion": (
        "Servicio de mantenimiento preventivo y correctivo de equipos de "
        "aire acondicionado de la sede central"
    ),
    "area_sigla": AREA_SIGLA,
    "numero_orden": "OS-2026-00300",
    "fecha_requerimiento": date(2026, 7, 20),
    "fecha_orden": date(2026, 8, 3),
    "fecha_inicio_prestacion": date(2026, 8, 4),
    "plazo_dias": 45,
    "fecha_entrega_real": date(2026, 9, 29),
    "monto": Decimal("48000.00"),
}
