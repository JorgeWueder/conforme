"""R3: la conformidad se emitió fuera del plazo general o especial registrado."""
from conforme import normativa
from conforme.reglas.modelo import AlertaPropuesta, FotoExpediente, dias, fecha


def evaluar(foto: FotoExpediente) -> list[AlertaPropuesta]:
    if foto.conformidad is None or foto.fecha_entrega_real is None:
        return []
    transcurridos = (foto.conformidad.fecha_conformidad - foto.fecha_entrega_real).days
    maximo = normativa.plazo_conformidad(foto.conformidad_plazo_especial)
    if transcurridos <= maximo:
        return []
    return [AlertaPropuesta(
        regla="R3",
        clave="conformidad-tardia",
        explicacion=(
            f"La entrega fue el {fecha(foto.fecha_entrega_real)} y la conformidad se emitió "
            f"el {fecha(foto.conformidad.fecha_conformidad)}: {dias(transcurridos)} después. "
            f"El máximo considerado es de {dias(maximo)} ({dias(transcurridos - maximo)} de exceso)."
        ),
        datos={"dias_transcurridos": transcurridos, "dias_maximo": maximo},
        persona_implicada_id=foto.conformidad.conformante_id,
    )]
