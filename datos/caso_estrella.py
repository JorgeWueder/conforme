"""Caso estrella de la demo, hecho a mano.

Servicio de S/ 48,000 a 45 días, entregado 12 días tarde.
Fecha límite = 3 ago + 45 días = 17 sep 2026; entrega real = 29 sep 2026.
Penalidad esperada = 12 × (0.10 × 48,000) / (0.40 × 45) = S/ 3,200 (tope S/ 4,800).

La conformidad la da la misma persona que solicitó, sin penalidad y con un
entregable sin evidencia: debe salir en rojo con R1, R2 y R4 (y nada más).
Sin pago: en la demo, tesorería lo ve antes de pagar.
"""
from datetime import date
from decimal import Decimal

CODIGO = "EXP-2026-0300"
AREA_SIGLA = "INF"
USERNAME_SOLICITANTE = "inf1"
USERNAME_CONFORMANTE = "inf1"

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

ENTREGABLES = [
    "Informe de diagnóstico inicial de los equipos",
    "Acta de ejecución del mantenimiento de 24 equipos",
    "Informe final con registro fotográfico",
]
ENTREGABLE_SIN_EVIDENCIA = 3

CONFORMIDAD = {
    "fecha_conformidad": date(2026, 10, 2),  # 3 días después de la entrega: no activa R3
    "penalidad_aplicada": Decimal("0.00"),
    "observaciones": "Servicio recibido a satisfacción.",
}

ANOMALIAS = [
    ("R1", "Caso estrella: el entregable 3 se dio por cumplido sin evidencia."),
    ("R2", "Caso estrella: 12 días de atraso, penalidad esperada S/ 3,200.00, aplicada S/ 0.00."),
    ("R4", "Caso estrella: solicitante y conformante son la misma persona."),
]
