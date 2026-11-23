"""R6: el mismo proveedor se repite en el mismo área dentro de una ventana corta.

Alerta en el expediente que alcanza el umbral, es decir, en el tercero (por
defecto) y siguientes de esa serie, ordenados por fecha de orden y luego por id.
Los anteriores no se alertan: así una alerta nunca depende de expedientes
posteriores y no queda desactualizada. Umbral y ventana en normativa.py
(POR VERIFICAR). Es una señal para revisar, no prueba una irregularidad.
"""
from conforme import normativa
from conforme.reglas.modelo import AlertaPropuesta, FotoExpediente, dias, fecha, soles


def evaluar(foto: FotoExpediente) -> list[AlertaPropuesta]:
    ventana = normativa.R6_VENTANA_DIAS
    previos = sorted(
        (v for v in foto.previos_mismo_proveedor
         if (foto.fecha_orden - v.fecha_orden).days <= ventana),
        key=lambda v: (v.fecha_orden, v.expediente_id),
    )
    total = len(previos) + 1
    if total < normativa.R6_MINIMO_EXPEDIENTES:
        return []
    suma = foto.monto + sum(v.monto for v in previos)
    transcurridos = (foto.fecha_orden - previos[0].fecha_orden).days
    anteriores = "; ".join(f"{v.codigo} (orden del {fecha(v.fecha_orden)})" for v in previos)
    nombre = foto.proveedor or "El proveedor"
    return [AlertaPropuesta(
        regla="R6",
        clave="proveedor-recurrente",
        explicacion=(
            f"{nombre} figura en {total} expedientes de la misma área con órdenes en "
            f"{dias(transcurridos)}: {anteriores}; y este ({foto.codigo}, orden del "
            f"{fecha(foto.fecha_orden)}). Suma de montos: {soles(suma)}. "
            f"Se alerta desde {normativa.R6_MINIMO_EXPEDIENTES} expedientes en "
            f"{dias(ventana)}. Es una señal para revisar cómo se eligió al proveedor, "
            "no prueba una irregularidad."
        ),
        datos={
            "proveedor_id": foto.proveedor_id,
            "expedientes": total,
            "dias_entre_primera_y_esta": transcurridos,
            "minimo": normativa.R6_MINIMO_EXPEDIENTES,
            "ventana_dias": ventana,
            "anteriores": [v.codigo for v in previos],
            "suma_montos": str(suma),
        },
        persona_implicada_id=foto.solicitante_id,
    )]
