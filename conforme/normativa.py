"""Reglas del MVP para bienes y servicios bajo el Reglamento de la Ley 32069."""
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

# Artículos 119, 120 y 229: estimación por el monto y plazo de la orden del MVP.
PENALIDAD_COEFICIENTE = Decimal("0.10")
PENALIDAD_FACTOR_BIENES_SERVICIOS = Decimal("0.40")
PENALIDAD_TOPE_PORCENTAJE = Decimal("0.10")  # tope: 10 % del monto
PENALIDAD_TOLERANCIA = Decimal("0.01")       # diferencia que no se alerta

# Artículo 144.3: días desde el día siguiente de recibido el entregable.
CONFORMIDAD_PLAZO_MAXIMO_DIAS = 7
CONFORMIDAD_PLAZO_ESPECIAL_DIAS = 20
R4_CLAVE_ANTERIOR = "misma-persona"


def plazo_conformidad(especial: bool) -> int:
    return CONFORMIDAD_PLAZO_ESPECIAL_DIAS if especial else CONFORMIDAD_PLAZO_MAXIMO_DIAS

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
    "R2": "Posible penalidad por mora pendiente",
    "R3": "Conformidad tardía",
    "R4": "Misma persona en conformidad y registro de pago",
    "R5": "Pago registrado sin conformidad previa",
    "R6": "Proveedor recurrente en la misma área",
    "R7": "Compras similares sucesivas al mismo proveedor",
    "R8": "Fechas incoherentes en el expediente",
}

_CENTIMOS = Decimal("0.01")


def _redondear(monto: Decimal) -> Decimal:
    return monto.quantize(_CENTIMOS, rounding=ROUND_HALF_UP)


def fecha_limite(fecha_orden: date, plazo_dias: int, inicio: date | None = None) -> date:
    """El inicio pactado cuenta como primer día. Sin ese dato se estima desde la orden."""
    if inicio is not None:
        return inicio + timedelta(days=plazo_dias - 1)
    return fecha_orden + timedelta(days=plazo_dias)


def dias_de_atraso(
    fecha_orden: date, plazo_dias: int, fecha_entrega_real: date, inicio: date | None = None,
) -> int:
    return max(0, (fecha_entrega_real - fecha_limite(fecha_orden, plazo_dias, inicio)).days)


def penalidad_diaria(monto: Decimal, plazo_dias: int) -> Decimal:
    """Sin redondear: el redondeo se hace sobre el total."""
    return (PENALIDAD_COEFICIENTE * monto) / (PENALIDAD_FACTOR_BIENES_SERVICIOS * plazo_dias)


def penalidad_tope(monto: Decimal) -> Decimal:
    return _redondear(PENALIDAD_TOPE_PORCENTAJE * monto)


def penalidad_esperada(monto: Decimal, plazo_dias: int, dias_atraso: int) -> Decimal:
    if dias_atraso <= 0:
        return Decimal("0.00")
    calculada = _redondear(penalidad_diaria(monto, plazo_dias) * dias_atraso)
    return min(calculada, penalidad_tope(monto))

# --- Evaluación de posibles proveedores (Fase 2). ------------------------------------
# POR VERIFICAR: umbrales de trabajo del equipo, no fijados por la Ley 32069 ni su
# Reglamento. Sirven para ordenar la revisión; ninguno descalifica por sí solo salvo
# los impedimentos (inhabilitación vigente, contribuyente no habido o de baja).
EMPRESA_ANTIGUEDAD_MINIMA_MESES = 12      # menos de esto: empresa reciente, se revisa
PRECIO_SOBREPRECIO_REVISAR = Decimal("0.15")   # 15 % sobre el valor estimado
PRECIO_SOBREPRECIO_ALERTA = Decimal("0.30")
PRECIO_BAJO_REVISAR = Decimal("0.25")         # 25 % bajo el estimado: posible precio temerario
PRECIO_BAJO_ALERTA = Decimal("0.45")
PRECIO_COTIZACIONES_GEMELAS = Decimal("0.01")  # dos cotizaciones a menos de 1 % entre sí
DESEMPENO_PENALIDADES_REVISAR = 1
DESEMPENO_PENALIDADES_ALERTA = 3
DESEMPENO_CONCENTRACION_ORDENES_12M = 4   # órdenes con la entidad en los últimos 12 meses

# --- Revisión documental y forense (Fase 3). -----------------------------------------
# IGV: 16 % más 2 % del Impuesto de Promoción Municipal (TUO de la Ley del IGV, D.S. 055-99-EF).
IGV_TASA = Decimal("0.18")
CUADRE_TOLERANCIA = Decimal("0.05")   # diferencias de redondeo que no se señalan
# POR VERIFICAR: criterios de trabajo, no normativos. Umbrales de MAD para el primer
# dígito según Nigrini (Benford's Law, 2012); muestra mínima y rango definidos por el equipo.
BENFORD_MUESTRA_MINIMA = 30
BENFORD_RANGO_MINIMO = 100            # el mayor monto debe ser al menos 100 veces el menor
BENFORD_MAD_CONFORME = 0.006
BENFORD_MAD_ACEPTABLE = 0.012
BENFORD_MAD_MARGINAL = 0.015
BENFORD_EXCESO_DIGITO = 0.04          # 4 puntos por encima de lo esperado
DOCUMENTOS_GEMELOS_MINUTOS = 30       # archivos de postores distintos creados con poca diferencia
SIMILITUD_REVISAR = Decimal("0.25")
SIMILITUD_ALERTA = Decimal("0.45")
TDR_ACREDITADO = Decimal("0.6")       # fracción de términos del entregable presentes en la propuesta
TDR_INCOMPLETO = Decimal("0.4")
