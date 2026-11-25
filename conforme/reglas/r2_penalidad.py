"""R2: estima la diferencia que corresponde revisar si el atraso es imputable."""
from conforme import normativa
from conforme.reglas.modelo import AlertaPropuesta, FotoExpediente, dias, fecha, soles


def evaluar(foto: FotoExpediente) -> list[AlertaPropuesta]:
    if foto.conformidad is None or foto.fecha_entrega_real is None:
        return []
    limite = normativa.fecha_limite(foto.fecha_orden, foto.plazo_dias, foto.fecha_inicio_prestacion)
    atraso = (foto.fecha_entrega_real - limite).days
    if atraso <= 0:
        return []
    diaria = normativa.penalidad_diaria(foto.monto, foto.plazo_dias)
    calculada = normativa._redondear(diaria * atraso)
    tope = normativa.penalidad_tope(foto.monto)
    esperada = normativa.penalidad_esperada(foto.monto, foto.plazo_dias, atraso)
    aplicada = foto.conformidad.penalidad_aplicada
    if esperada - aplicada <= normativa.PENALIDAD_TOLERANCIA:
        return []

    calculo = f"{dias(atraso)} de atraso × {soles(diaria)} por día = {soles(calculada)}"
    if calculada > tope:
        calculo += f", con un tope de {soles(tope)}"
    else:
        calculo += f" (tope {soles(tope)})"
    return [AlertaPropuesta(
        regla="R2",
        clave="penalidad",
        explicacion=(
            f"La fecha límite considerada es el {fecha(limite)} y la entrega se recibió el "
            f"{fecha(foto.fecha_entrega_real)}. {calculo}. "
            f"Importe aplicado: {soles(aplicada)}. Diferencia estimada: {soles(esperada - aplicada)}. "
            "Revisar si el atraso es imputable al proveedor y si corresponde la penalidad según la orden."
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
