"""R2: hubo atraso en la entrega y la penalidad aplicada es menor que la esperada.

La fórmula y sus constantes están en normativa.py (POR VERIFICAR).
"""
from conforme import normativa
from conforme.reglas.modelo import AlertaPropuesta, FotoExpediente, dias, fecha, soles


def evaluar(foto: FotoExpediente) -> list[AlertaPropuesta]:
    if foto.conformidad is None or foto.fecha_entrega_real is None:
        return []
    atraso = normativa.dias_de_atraso(foto.fecha_orden, foto.plazo_dias, foto.fecha_entrega_real)
    if atraso == 0:
        return []
    diaria = normativa.penalidad_diaria(foto.monto, foto.plazo_dias)
    calculada = normativa._redondear(diaria * atraso)
    tope = normativa.penalidad_tope(foto.monto)
    esperada = normativa.penalidad_esperada(foto.monto, foto.plazo_dias, atraso)
    aplicada = foto.conformidad.penalidad_aplicada
    if esperada - aplicada <= normativa.PENALIDAD_TOLERANCIA:
        return []

    limite = normativa.fecha_limite(foto.fecha_orden, foto.plazo_dias)
    calculo = f"{dias(atraso)} de atraso × {soles(diaria)} por día = {soles(calculada)}"
    if calculada > tope:
        calculo += f", que supera el tope de {soles(tope)}; se esperan {soles(esperada)}"
    else:
        calculo += f" esperados (tope {soles(tope)})"
    return [AlertaPropuesta(
        regla="R2",
        clave="penalidad",
        explicacion=(
            f"La entrega venció el {fecha(limite)} y se recibió el "
            f"{fecha(foto.fecha_entrega_real)}. {calculo}; aplicado {soles(aplicada)}. "
            f"Diferencia: {soles(esperada - aplicada)}."
        ),
        datos={
            "dias_atraso": atraso,
            "penalidad_diaria": str(normativa._redondear(diaria)),
            "penalidad_esperada": str(esperada),
            "penalidad_aplicada": str(aplicada),
            "tope": str(tope),
        },
        persona_implicada_id=foto.conformidad.conformante_id,
    )]
