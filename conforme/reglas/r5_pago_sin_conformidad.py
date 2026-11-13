"""R5: se registró un pago sin conformidad, o con conformidad de fecha posterior."""
from conforme.reglas.modelo import AlertaPropuesta, FotoExpediente, dias, fecha, soles


def evaluar(foto: FotoExpediente) -> list[AlertaPropuesta]:
    propuestas = []
    for pago in foto.pagos:
        datos = {"pago_id": pago.id, "fecha_pago": str(pago.fecha_pago), "monto": str(pago.monto)}
        if foto.conformidad is None:
            explicacion = (
                f"Se registró un pago de {soles(pago.monto)} el {fecha(pago.fecha_pago)} "
                "y el expediente no tiene conformidad registrada."
            )
        elif foto.conformidad.fecha_conformidad > pago.fecha_pago:
            despues = (foto.conformidad.fecha_conformidad - pago.fecha_pago).days
            datos["fecha_conformidad"] = str(foto.conformidad.fecha_conformidad)
            explicacion = (
                f"Se registró un pago de {soles(pago.monto)} el {fecha(pago.fecha_pago)}, "
                f"pero la conformidad tiene fecha {fecha(foto.conformidad.fecha_conformidad)}: "
                f"{dias(despues)} después del pago."
            )
        else:
            continue
        propuestas.append(AlertaPropuesta(
            regla="R5",
            clave=f"pago-{pago.id}",
            explicacion=explicacion,
            datos=datos,
            persona_implicada_id=pago.registrado_por,
        ))
    return propuestas
