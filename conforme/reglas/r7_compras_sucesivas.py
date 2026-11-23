"""R7: la misma prestación se contrata otra vez, al mismo proveedor y en la misma
área, poco tiempo después.

Es una señal de posible fraccionamiento. «La misma prestación» es la misma
descripción, sin distinguir mayúsculas ni espacios repetidos: no se comparan
textos parecidos. Alerta en el expediente que alcanza el umbral (el segundo por
defecto) y siguientes, ordenados por fecha de orden y luego por id. Umbral y
ventana en normativa.py (POR VERIFICAR).
"""
from conforme import normativa
from conforme.reglas.modelo import AlertaPropuesta, FotoExpediente, dias, fecha, soles


def _normalizar(texto: str) -> str:
    return " ".join(texto.lower().split())


def evaluar(foto: FotoExpediente) -> list[AlertaPropuesta]:
    if not foto.descripcion.strip():
        return []
    ventana = normativa.R7_VENTANA_DIAS
    objetivo = _normalizar(foto.descripcion)
    previos = sorted(
        (v for v in foto.previos_mismo_proveedor
         if _normalizar(v.descripcion) == objetivo
         and (foto.fecha_orden - v.fecha_orden).days <= ventana),
        key=lambda v: (v.fecha_orden, v.expediente_id),
    )
    total = len(previos) + 1
    if total < normativa.R7_MINIMO_EXPEDIENTES:
        return []
    suma = foto.monto + sum(v.monto for v in previos)
    transcurridos = (foto.fecha_orden - previos[0].fecha_orden).days
    anteriores = "; ".join(
        f"{v.codigo} ({soles(v.monto)}, orden del {fecha(v.fecha_orden)})" for v in previos)
    nombre = foto.proveedor or "el mismo proveedor"
    return [AlertaPropuesta(
        regla="R7",
        clave="compras-sucesivas",
        explicacion=(
            f"«{foto.descripcion.strip()}» se contrató {total} veces a {nombre} en la "
            f"misma área, con órdenes en {dias(transcurridos)}: {anteriores}; y este "
            f"({foto.codigo}, {soles(foto.monto)}, orden del {fecha(foto.fecha_orden)}). "
            f"Suma de montos: {soles(suma)}. Se alerta desde "
            f"{normativa.R7_MINIMO_EXPEDIENTES} compras en {dias(ventana)}. Puede indicar "
            "una compra dividida en partes; también puede ser una necesidad recurrente "
            "legítima: lo decide una persona."
        ),
        datos={
            "proveedor_id": foto.proveedor_id,
            "compras": total,
            "dias_entre_primera_y_esta": transcurridos,
            "minimo": normativa.R7_MINIMO_EXPEDIENTES,
            "ventana_dias": ventana,
            "anteriores": [v.codigo for v in previos],
            "suma_montos": str(suma),
        },
        persona_implicada_id=foto.solicitante_id,
    )]
