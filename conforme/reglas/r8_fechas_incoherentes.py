"""R8: las fechas del expediente no son coherentes entre sí.

La aplicación ya rechaza varias de estas combinaciones al registrarlas (orden anterior
al requerimiento, entrega anterior a la orden, conformidad anterior a la entrega, pago
anterior a la orden). Esta regla las detecta si los datos entraron o cambiaron por otro
camino (carga masiva, edición directa), y revisa además la entrega anterior al inicio
de la prestación, que la aplicación no valida. Una alerta por tipo de incoherencia; el
pago anterior a la conformidad es de R5 y no se repite aquí.
"""
from conforme.reglas.modelo import AlertaPropuesta, FotoExpediente, fecha


def evaluar(foto: FotoExpediente) -> list[AlertaPropuesta]:
    conformante = foto.conformidad.conformante_id if foto.conformidad else None
    propuestas = []

    def agregar(clave, explicacion, datos, persona):
        propuestas.append(AlertaPropuesta(
            regla="R8", clave=clave, explicacion=explicacion, datos=datos,
            persona_implicada_id=persona))

    if foto.fecha_requerimiento is not None and foto.fecha_orden < foto.fecha_requerimiento:
        agregar(
            "orden-antes-de-requerimiento",
            f"La orden tiene fecha {fecha(foto.fecha_orden)} y el requerimiento "
            f"{fecha(foto.fecha_requerimiento)}: la orden figura antes de que se pidiera "
            "el bien o servicio.",
            {"fecha_orden": str(foto.fecha_orden),
             "fecha_requerimiento": str(foto.fecha_requerimiento)},
            foto.solicitante_id,
        )

    entrega = foto.fecha_entrega_real
    if entrega is not None:
        if entrega < foto.fecha_orden:
            agregar(
                "entrega-antes-de-orden",
                f"La entrega real es del {fecha(entrega)} y la orden del "
                f"{fecha(foto.fecha_orden)}: se entregó antes de que existiera la orden.",
                {"fecha_entrega_real": str(entrega), "fecha_orden": str(foto.fecha_orden)},
                conformante,
            )
        inicio = foto.fecha_inicio_prestacion
        if inicio is not None and entrega < inicio:
            agregar(
                "entrega-antes-de-inicio",
                f"La entrega real es del {fecha(entrega)} y el inicio de la prestación "
                f"del {fecha(inicio)}: se entregó antes de empezar.",
                {"fecha_entrega_real": str(entrega), "fecha_inicio_prestacion": str(inicio)},
                conformante,
            )
        if foto.conformidad is not None and foto.conformidad.fecha_conformidad < entrega:
            agregar(
                "conformidad-antes-de-entrega",
                f"La conformidad tiene fecha {fecha(foto.conformidad.fecha_conformidad)} y la "
                f"entrega real es del {fecha(entrega)}: se dio conformidad antes de recibir.",
                {"fecha_conformidad": str(foto.conformidad.fecha_conformidad),
                 "fecha_entrega_real": str(entrega)},
                conformante,
            )

    for pago in foto.pagos:
        if pago.fecha_pago < foto.fecha_orden:
            agregar(
                f"pago-antes-de-orden-{pago.id}",
                f"Se registró un pago con fecha {fecha(pago.fecha_pago)}, anterior a la "
                f"orden del {fecha(foto.fecha_orden)}.",
                {"pago_id": pago.id, "fecha_pago": str(pago.fecha_pago),
                 "fecha_orden": str(foto.fecha_orden)},
                pago.registrado_por,
            )
    return propuestas
