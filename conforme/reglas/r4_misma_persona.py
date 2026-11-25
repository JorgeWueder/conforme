"""R4: la persona que otorgó la conformidad también figura en el registro del pago."""
from conforme.reglas.modelo import AlertaPropuesta, FotoExpediente


def evaluar(foto: FotoExpediente) -> list[AlertaPropuesta]:
    conformidad = foto.conformidad
    if conformidad is None:
        return []
    return [AlertaPropuesta(
        regla="R4",
        clave=f"conformidad-y-pago-{pago.id}",
        explicacion=(
            f"{conformidad.conformante} otorgó la conformidad y figura como responsable "
            "del registro del pago. Revisar la asignación de funciones."
        ),
        datos={"persona_id": conformidad.conformante_id, "pago_id": pago.id},
        persona_implicada_id=conformidad.conformante_id,
    ) for pago in foto.pagos if pago.registrado_por == conformidad.conformante_id]
