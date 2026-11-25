"""Caso estrella de la demo, hecho a mano.

Servicio de S/ 43,200 a 45 días. El plazo empieza el 4 de agosto, vence el 17 de
septiembre y el proveedor entrega el 29. La penalidad estimada es S/ 2,880.
El docente que solicitó el servicio da la conformidad con un entregable sin
evidencia y sin penalidad registrada (R1 y R2). Tesorería lo ve antes del pago.
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
        "Mantenimiento preventivo de equipos del laboratorio de Ingeniería Química"
    ),
    "area_sigla": AREA_SIGLA,
    "numero_orden": "OS-2026-00300",
    "proyecto_referencia": "PIC-2026-018",
    "fecha_requerimiento": date(2026, 7, 20),
    "fecha_orden": date(2026, 8, 3),
    "fecha_inicio_prestacion": date(2026, 8, 4),
    "plazo_dias": 45,
    "fecha_entrega_real": date(2026, 9, 29),
    "monto": Decimal("43200.00"),
}

ENTREGABLES = [
    "Diagnóstico y ficha de inventario de los equipos",
    "Acta de mantenimiento preventivo firmada",
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
    ("R2", "Caso estrella: 12 días de atraso, penalidad estimada S/ 2,880.00, aplicada S/ 0.00."),
]
