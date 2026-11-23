"""Parámetros normativos usados por las reglas.

TODO lo marcado "POR VERIFICAR" es un supuesto de trabajo que debe contrastarse
con el Reglamento de contrataciones vigente antes de cualquier uso real. Están
aislados aquí para que corregirlos sea cambiar una constante. Ver PLAN.md.
"""
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

# --- Penalidad por mora (R2). POR VERIFICAR con el Reglamento. ---------------
# penalidad diaria = (COEFICIENTE x monto) / (F x plazo en días)
PENALIDAD_COEFICIENTE = Decimal("0.10")
PENALIDAD_F_PLAZO_CORTO = Decimal("0.40")   # plazos de hasta PLAZO_CORTE días
PENALIDAD_F_PLAZO_LARGO = Decimal("0.25")   # plazos mayores
PENALIDAD_PLAZO_CORTE_DIAS = 60
PENALIDAD_TOPE_PORCENTAJE = Decimal("0.10")  # tope: 10 % del monto
PENALIDAD_TOLERANCIA = Decimal("0.01")       # diferencia que no se alerta

# --- Conformidad tardía (R3). POR VERIFICAR con el Reglamento. ---------------
# Días calendario máximos entre la entrega real y la conformidad.
CONFORMIDAD_PLAZO_MAXIMO_DIAS = 7

# --- Recurrencia de proveedor (R6). POR VERIFICAR: umbrales de trabajo, no normativos. ---
# Alerta si el mismo proveedor figura en al menos R6_MINIMO_EXPEDIENTES expedientes
# del mismo área (contando el que se evalúa) con órdenes dentro de R6_VENTANA_DIAS días.
R6_MINIMO_EXPEDIENTES = 3
R6_VENTANA_DIAS = 90

# --- Compras similares sucesivas (R7). POR VERIFICAR: umbrales de trabajo. ----
# Alerta si el mismo proveedor y el mismo área repiten la misma prestación (misma
# descripción, sin distinguir mayúsculas ni espacios) en al menos R7_MINIMO_EXPEDIENTES
# expedientes con órdenes dentro de R7_VENTANA_DIAS días. Es una señal de posible
# fraccionamiento: no se compara con ningún umbral de monto del Reglamento.
R7_MINIMO_EXPEDIENTES = 2
R7_VENTANA_DIAS = 60

# Ventana más amplia que necesitan las reglas entre expedientes (el motor la usa
# para cargar los expedientes anteriores del mismo proveedor y área).
VENTANA_MAXIMA_ENTRE_EXPEDIENTES_DIAS = max(R6_VENTANA_DIAS, R7_VENTANA_DIAS)

# --- Severidades (propuesta del equipo, configurable). -----------------------
SEVERIDAD_ALTA = "alta"
SEVERIDAD_MEDIA = "media"
SEVERIDAD_POR_REGLA = {
    "R1": SEVERIDAD_ALTA,
    "R2": SEVERIDAD_MEDIA,
    "R3": SEVERIDAD_MEDIA,
    "R4": SEVERIDAD_ALTA,
    "R5": SEVERIDAD_ALTA,
    "R6": SEVERIDAD_MEDIA,
    "R7": SEVERIDAD_MEDIA,
    "R8": SEVERIDAD_MEDIA,
}
NOMBRE_REGLA = {
    "R1": "Entregable sin evidencia",
    "R2": "Penalidad por atraso no aplicada",
    "R3": "Conformidad tardía",
    "R4": "Solicitante y conformante son la misma persona",
    "R5": "Pago sin conformidad previa",
    "R6": "Proveedor recurrente en la misma área",
    "R7": "Compras similares sucesivas al mismo proveedor",
    "R8": "Fechas incoherentes en el expediente",
}

_CENTIMOS = Decimal("0.01")


def _redondear(monto: Decimal) -> Decimal:
    return monto.quantize(_CENTIMOS, rounding=ROUND_HALF_UP)


def fecha_limite(fecha_orden: date, plazo_dias: int) -> date:
    """Fecha de la orden + plazo en días calendario. POR VERIFICAR."""
    return fecha_orden + timedelta(days=plazo_dias)


def dias_de_atraso(fecha_orden: date, plazo_dias: int, fecha_entrega_real: date) -> int:
    return max(0, (fecha_entrega_real - fecha_limite(fecha_orden, plazo_dias)).days)


def penalidad_diaria(monto: Decimal, plazo_dias: int) -> Decimal:
    """Sin redondear: el redondeo se hace sobre el total."""
    f = (PENALIDAD_F_PLAZO_CORTO if plazo_dias <= PENALIDAD_PLAZO_CORTE_DIAS
         else PENALIDAD_F_PLAZO_LARGO)
    return (PENALIDAD_COEFICIENTE * monto) / (f * plazo_dias)


def penalidad_tope(monto: Decimal) -> Decimal:
    return _redondear(PENALIDAD_TOPE_PORCENTAJE * monto)


def penalidad_esperada(monto: Decimal, plazo_dias: int, dias_atraso: int) -> Decimal:
    if dias_atraso <= 0:
        return Decimal("0.00")
    calculada = _redondear(penalidad_diaria(monto, plazo_dias) * dias_atraso)
    return min(calculada, penalidad_tope(monto))
