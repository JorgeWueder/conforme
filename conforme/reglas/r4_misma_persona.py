"""R4: quien solicitó el bien o servicio es quien dio la conformidad."""
from conforme.reglas.modelo import AlertaPropuesta, FotoExpediente


def evaluar(foto: FotoExpediente) -> list[AlertaPropuesta]:
    conformidad = foto.conformidad
    if conformidad is None or conformidad.conformante_id != foto.solicitante_id:
        return []
    return [AlertaPropuesta(
        regla="R4",
        clave="misma-persona",
        explicacion=(
            f"{conformidad.conformante} figura como solicitante del requerimiento y también "
            "como quien dio la conformidad. No hay una segunda persona que confirme la recepción."
        ),
        datos={"persona_id": conformidad.conformante_id},
        persona_implicada_id=conformidad.conformante_id,
    )]
