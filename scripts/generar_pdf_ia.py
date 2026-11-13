"""Regenera el PDF sintético de términos de referencia y su resultado de respaldo.

Uso:  python -m scripts.generar_pdf_ia      (necesita reportlab: requirements-dev.txt)

Escribe datos/respaldo_ia/terminos_referencia.pdf y .json. Ambos se versionan:
la aplicación no necesita reportlab.
"""
import json

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from conforme.ia.extractor import PDF_EJEMPLO, RESPALDO_JSON

TITULO = "TÉRMINOS DE REFERENCIA"
SUBTITULO = "Servicio de mantenimiento de equipos de cómputo y red de la sede central"
ENTREGABLES = [
    "Informe de diagnóstico del estado de 60 equipos de cómputo y 8 switches",
    "Acta de mantenimiento preventivo de los equipos de cómputo",
    "Acta de reemplazo de componentes defectuosos con su garantía",
    "Informe final con recomendaciones y registro fotográfico",
]
PLAZO_DIAS = 30
PENALIDADES = [
    "Penalidad por mora en la ejecución de la prestación, de 0.10 x monto / (0.40 x plazo) "
    "por cada día de atraso, hasta un máximo del 10 % del monto contratado.",
    "Penalidad por no presentar el informe final dentro de los 5 días posteriores al "
    "término del servicio.",
]


def _parrafo(c, texto, y, ancho=88, tamano=11):
    c.setFont("Helvetica", tamano)
    linea = ""
    for palabra in texto.split():
        if len(linea) + len(palabra) + 1 > ancho:
            c.drawString(60, y, linea)
            y -= 15
            linea = palabra
        else:
            linea = f"{linea} {palabra}".strip()
    c.drawString(60, y, linea)
    return y - 20


def main():
    PDF_EJEMPLO.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(PDF_EJEMPLO), pagesize=A4)
    c.setTitle("Términos de referencia (documento sintético)")
    c.setFont("Helvetica-Bold", 16)
    c.drawString(60, 790, TITULO)
    y = _parrafo(c, SUBTITULO, 765, tamano=12)
    y = _parrafo(c, "Documento sintético de demostración. No corresponde a ninguna contratación real.",
                 y, tamano=9)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(60, y, "1. Entregables")
    y -= 22
    for i, entregable in enumerate(ENTREGABLES, start=1):
        y = _parrafo(c, f"{i}. {entregable}.", y)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(60, y, "2. Plazo de ejecución")
    y = _parrafo(c, f"El plazo de ejecución es de {PLAZO_DIAS} días calendario contados desde "
                    "el día siguiente de la notificación de la orden de servicio.", y - 22)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(60, y, "3. Penalidades")
    y -= 22
    for penalidad in PENALIDADES:
        y = _parrafo(c, f"- {penalidad}", y)
    c.save()

    RESPALDO_JSON.write_text(json.dumps({
        "entregables": [{"numero": i, "descripcion": e} for i, e in enumerate(ENTREGABLES, 1)],
        "plazo_dias": PLAZO_DIAS,
        "penalidades": PENALIDADES,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Escritos {PDF_EJEMPLO.name} y {RESPALDO_JSON.name}.")


if __name__ == "__main__":
    main()
