"""R1: se dio por cumplido un entregable sin adjuntar evidencia."""
from conforme.reglas.modelo import AlertaPropuesta, FotoExpediente


def evaluar(foto: FotoExpediente) -> list[AlertaPropuesta]:
    if foto.conformidad is None:
        return []
    cumplidos = [e for e in foto.entregables if e.cumplido]
    sin_evidencia = [e for e in cumplidos if e.n_evidencias == 0]
    if not sin_evidencia:
        return []
    lista = "; ".join(f"n.º {e.numero} «{e.descripcion}»" for e in sin_evidencia)
    if len(sin_evidencia) == 1:
        inicio = f"1 de {len(cumplidos)} entregables dados por cumplidos no tiene evidencia adjunta"
    else:
        inicio = (f"{len(sin_evidencia)} de {len(cumplidos)} entregables dados por cumplidos "
                  "no tienen evidencia adjunta")
    return [AlertaPropuesta(
        regla="R1",
        clave="sin-evidencia",
        explicacion=f"{inicio}: {lista}.",
        datos={
            "entregables_cumplidos": len(cumplidos),
            "sin_evidencia": [e.numero for e in sin_evidencia],
        },
        persona_implicada_id=foto.conformidad.conformante_id,
    )]
