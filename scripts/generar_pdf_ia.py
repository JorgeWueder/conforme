"""Regenera el PDF de términos de referencia (formato institucional de 2 páginas) y su respaldo.

Uso:  python -m scripts.generar_pdf_ia      (necesita reportlab: requirements-dev.txt)

Escribe datos/respaldo_ia/terminos_referencia.pdf y .json.
"""
import json

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from conforme.ia.extractor import PDF_EJEMPLO, RESPALDO_JSON

AZUL = colors.HexColor("#003477")
AZUL_CLARO = colors.HexColor("#EAF2FC")
DORADO = colors.HexColor("#D49B27")
GRIS_TEXTO = colors.HexColor("#1E293B")
GRIS_SUAVE = colors.HexColor("#64748B")
BORDE = colors.HexColor("#CBD5E1")

OBJETO = "Servicio de limpieza y desinfección de ambientes de la sede central"
PLAZO_DIAS = 15

ENTREGABLES = [
    (
        "Plan de trabajo y cronograma de limpieza por ambiente",
        "Día 2",
        "Plan técnico firmado por el supervisor, con relación de ambientes, horarios y personal asignado.",
    ),
    (
        "Acta de desinfección de ambientes críticos con los productos utilizados",
        "Día 10",
        "Acta suscrita por el contratista y el responsable del área indicando ambientes atendidos y lotes.",
    ),
    (
        "Certificado de los insumos y productos empleados",
        "Día 12",
        "Autorizaciones sanitarias DIGESA vigentes y hojas de seguridad (MSDS) de los desinfectantes.",
    ),
    (
        "Informe final con recomendaciones y registro fotográfico",
        "Día 15",
        "Informe técnico consolidado con fotografías fechadas del antes y después por ambiente intervenido.",
    ),
]

PENALIDADES = [
    "Penalidad por mora en la ejecución de la prestación, de 0.10 x monto / (0.40 x plazo) "
    "por cada día de atraso, hasta un máximo del 10 % del monto contratado.",
    "Penalidad por no presentar el informe final dentro de los 3 días posteriores al "
    "término del servicio.",
    "Penalidad de 0.5 % del monto contratado por cada ocurrencia en que el personal ejecute "
    "labores sin equipo de protección personal (EPP) completo o sin señalización preventiva.",
]


def _pie_pagina(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(BORDE)
    canvas.setLineWidth(0.6)
    canvas.line(20 * mm, 16 * mm, A4[0] - 20 * mm, 16 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GRIS_SUAVE)
    canvas.drawString(20 * mm, 11.5 * mm, "Universidad Nacional de Trujillo · Unidad de Servicios Generales e Infraestructura")
    canvas.drawRightString(A4[0] - 20 * mm, 11.5 * mm, f"TDR · Página {doc.page}")
    canvas.restoreState()


def main():
    PDF_EJEMPLO.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(PDF_EJEMPLO),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=22 * mm,
        title=f"Términos de Referencia - {OBJETO}",
        author="Unidad de Servicios Generales e Infraestructura - UNT",
        subject=OBJETO,
    )

    base = getSampleStyleSheet()
    inst = ParagraphStyle("Inst", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=11,
                          leading=14, textColor=AZUL, alignment=TA_CENTER)
    subinst = ParagraphStyle("SubInst", parent=base["Normal"], fontName="Helvetica", fontSize=8.5,
                             leading=11, textColor=GRIS_SUAVE, alignment=TA_CENTER)
    titulo = ParagraphStyle("Titulo", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=14,
                            leading=18, textColor=AZUL, alignment=TA_CENTER, spaceBefore=6, spaceAfter=2)
    subtitulo = ParagraphStyle("Subtitulo", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=10.5,
                               leading=14, textColor=GRIS_TEXTO, alignment=TA_CENTER, spaceAfter=8)
    h2 = ParagraphStyle("H2", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=10.5,
                        leading=14, textColor=AZUL, spaceBefore=9, spaceAfter=3)
    cuerpo = ParagraphStyle("Cuerpo", parent=base["Normal"], fontName="Helvetica", fontSize=9.3,
                            leading=13.2, textColor=GRIS_TEXTO, alignment=TA_JUSTIFY, spaceAfter=4)
    viñeta = ParagraphStyle("Vineta", parent=cuerpo, leftIndent=12, firstLineIndent=-8, spaceAfter=2.5)
    celda = ParagraphStyle("Celda", parent=base["Normal"], fontName="Helvetica", fontSize=8.5,
                           leading=11.5, textColor=GRIS_TEXTO, alignment=TA_LEFT)
    celda_b = ParagraphStyle("CeldaB", parent=celda, fontName="Helvetica-Bold", textColor=AZUL)
    celda_th = ParagraphStyle("CeldaTH", parent=celda, fontName="Helvetica-Bold", textColor=colors.white)
    firma = ParagraphStyle("Firma", parent=base["Normal"], fontName="Helvetica", fontSize=8.8,
                           leading=12, textColor=GRIS_TEXTO, alignment=TA_CENTER)

    story = [
        Paragraph("UNIVERSIDAD NACIONAL DE TRUJILLO", inst),
        Paragraph("OFICINA DE INFRAESTRUCTURA · UNIDAD DE SERVICIOS GENERALES", subinst),
        Spacer(1, 2 * mm),
        HRFlowable(width="100%", thickness=2, color=AZUL, spaceAfter=1.5),
        HRFlowable(width="100%", thickness=1, color=DORADO, spaceAfter=6),
        Paragraph("TÉRMINOS DE REFERENCIA", titulo),
        Paragraph(OBJETO.upper(), subtitulo),
    ]

    ficha = Table(
        [
            [Paragraph("Área usuaria", celda_b),
             Paragraph("Unidad de Servicios Generales e Infraestructura", celda),
             Paragraph("Referencia POI", celda_b),
             Paragraph("PIC-2026-018", celda)],
            [Paragraph("Tipo de prestación", celda_b),
             Paragraph("Servicio general (contrato menor)", celda),
             Paragraph("Plazo de ejecución", celda_b),
             Paragraph(f"{PLAZO_DIAS} días calendario", celda)],
            [Paragraph("Lugar de prestación", celda_b),
             Paragraph("Sede Central — Ciudad Universitaria, Av. Juan Pablo II s/n, Trujillo", celda),
             Paragraph("Conformidad", celda_b),
             Paragraph("Hasta 7 días calendario", celda)],
        ],
        colWidths=[31 * mm, 66 * mm, 29 * mm, 44 * mm],
    )
    ficha.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), AZUL_CLARO),
        ("BACKGROUND", (2, 0), (2, -1), AZUL_CLARO),
        ("BOX", (0, 0), (-1, -1), 0.7, AZUL),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([ficha, Spacer(1, 4 * mm)])

    story.extend([
        Paragraph("1. Denominación de la contratación", h2),
        Paragraph(f"{OBJETO}, correspondiente a los ambientes administrativos, académicos de uso común y "
                  "servicios higiénicos priorizados de la Universidad Nacional de Trujillo.", cuerpo),

        Paragraph("2. Finalidad pública", h2),
        Paragraph("Garantizar condiciones óptimas de salubridad, higiene y bioseguridad en las instalaciones de la "
                  "Sede Central de la Universidad Nacional de Trujillo, reduciendo riesgos de contaminación "
                  "bacteriana y preservando la salud de estudiantes, docentes, personal administrativo y usuarios.", cuerpo),

        Paragraph("3. Objetivo de la contratación", h2),
        Paragraph("Contratar a una persona natural o jurídica especializada para ejecutar la limpieza profunda y "
                  "desinfección integral de ambientes críticos y de alto tránsito en la Sede Central, asegurando "
                  "el empleo de insumos con autorización sanitaria vigente y trazabilidad documental de cada etapa.", cuerpo),

        Paragraph("4. Alcance y descripción del servicio", h2),
        Paragraph("El servicio comprende un área aproximada de 2 450 m² distribuidos en el Pabellón Administrativo, "
                  "Auditorio Central, catorce (14) oficinas administrativas, seis (6) módulos de servicios higiénicos "
                  "y pasadizos de circulación interna. El contratista deberá ejecutar como mínimo las siguientes actividades:", cuerpo),
        Paragraph("• Limpieza previa en seco y barrido húmedo con paños de microfibra diferenciados por zona.", viñeta),
        Paragraph("• Lavado y desengrasado mecánico de pisos, zócalos, puertas, vidrios interiores y mobiliario.", viñeta),
        Paragraph("• Desinfección por aspersión y nebulización en frío utilizando amonio cuaternario de quinta "
                  "generación o equivalente, con registro sanitario vigente emitido por DIGESA, respetando los tiempos "
                  "de contacto y ventilación recomendados por el fabricante.", viñeta),
        Paragraph("• Desinfección profunda y desodorización de aparatos sanitarios, griferías y puntos de contacto frecuente.", viñeta),
        Paragraph("• Señalización preventiva de las áreas intervenidas y retiro controlado de envases y residuos generados.", viñeta),

        Paragraph("5. Requisitos del proveedor y del personal clave", h2),
        Paragraph("• Contar con RUC en estado ACTIVO y condición HABIDO, inscripción vigente en el Registro Nacional "
                  "de Proveedores (RNP — capítulo Servicios) y no encontrarse impedido para contratar con el Estado "
                  "conforme a la Ley N.º 32069 y su Reglamento.", viñeta),
        Paragraph("• Acreditar experiencia en servicios de limpieza y/o desinfección de ambientes institucionales o "
                  "comerciales mediante órdenes de servicio, contratos con conformidad o comprobantes cancelados.", viñeta),
        Paragraph("• Asignar como mínimo un (01) supervisor técnico y cuatro (04) operarios capacitados, todos con "
                  "Seguro Complementario de Trabajo de Riesgo (SCTR) vigente y equipo de protección personal (EPP) "
                  "completo: respirador con doble filtro, guantes de nitrilo, lentes, traje descartable y calzado antideslizante.", viñeta),

        Paragraph("6. Plazo de ejecución y lugar de prestación", h2),
        Paragraph(f"El plazo de ejecución es de {PLAZO_DIAS} días calendario contados a partir del día siguiente de la "
                  "notificación de la Orden de Servicio. Los trabajos se efectuarán en la Sede Central de la "
                  "Universidad Nacional de Trujillo (Av. Juan Pablo II s/n, Trujillo), en horarios coordinados con "
                  "la Unidad de Servicios Generales para no interrumpir la atención administrativa ni académica.", cuerpo),

        Paragraph("7. Entregables y medios de verificación", h2),
        Paragraph("El contratista deberá presentar los siguientes entregables en mesa de partes o por el canal "
                  "indicado por el área usuaria, acompañados de sus evidencias verificables:", cuerpo),
    ])

    filas_entregables = [[
        Paragraph("N.º", celda_th),
        Paragraph("Entregable", celda_th),
        Paragraph("Plazo", celda_th),
        Paragraph("Medio de verificación exigido", celda_th),
    ]]
    for i, (desc, dia, verificacion) in enumerate(ENTREGABLES, start=1):
        filas_entregables.append([
            Paragraph(str(i), celda_b),
            Paragraph(desc, celda),
            Paragraph(dia, celda),
            Paragraph(verificacion, celda),
        ])
    tabla_ent = Table(filas_entregables, colWidths=[11 * mm, 66 * mm, 18 * mm, 75 * mm], repeatRows=1)
    tabla_ent.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, AZUL_CLARO]),
        ("BOX", (0, 0), (-1, -1), 0.7, AZUL),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([tabla_ent, Spacer(1, 3 * mm)])

    story.extend([
        Paragraph("8. Conformidad de la prestación y forma de pago", h2),
        Paragraph("La conformidad del servicio será emitida por la Unidad de Servicios Generales e Infraestructura, "
                  "previa verificación del cumplimiento íntegro de los cuatro (4) entregables y sus respectivas "
                  "evidencias documentales y fotográficas, en un plazo máximo de siete (7) días calendario de "
                  "producida la recepción (artículo 144.3 del Reglamento de la Ley N.º 32069). El pago se realizará "
                  "en armada única, previa conformidad vigente, revisión favorable de la Oficina de Abastecimiento "
                  "y verificación obligatoria de Tesorería.", cuerpo),

        Paragraph("9. Penalidades aplicables", h2),
        Paragraph("En caso de retraso injustificado o incumplimiento de obligaciones durante la ejecución del servicio, "
                  "la entidad aplicará automáticamente las siguientes penalidades conforme a los artículos 119, 120 y "
                  "229 del Reglamento de la Ley N.º 32069:", cuerpo),
    ])
    for penalidad in PENALIDADES:
        story.append(Paragraph(f"• {penalidad}", viñeta))

    story.extend([
        Paragraph("10. Responsabilidad por vicios ocultos y cláusula anticorrupción", h2),
        Paragraph("La recepción conforme de la prestación no enerva el derecho de la entidad a reclamar posteriormente "
                  "por defectos o vicios ocultos por un plazo de un (1) año contado a partir de la conformidad. "
                  "El contratista declara y garantiza no haber ofrecido, negociado ni efectuado pago o beneficio "
                  "indebido alguno a funcionarios o servidores de la universidad en el marco de la presente contratación.", cuerpo),
        Spacer(1, 10 * mm),
        Table(
            [[Paragraph("________________________________________<br/><b>Jefatura de Servicios Generales e Infraestructura</b><br/>"
                        "Área Usuaria · Universidad Nacional de Trujillo", firma)]],
            colWidths=[110 * mm],
            hAlign="CENTER",
        ),
    ])

    doc.build(story, onFirstPage=_pie_pagina, onLaterPages=_pie_pagina)

    RESPALDO_JSON.write_text(json.dumps({
        "objeto": OBJETO,
        "corresponde_al_expediente": None,
        "motivo_discrepancia": "",
        "entregables": [{"numero": i, "descripcion": desc}
                        for i, (desc, _, _) in enumerate(ENTREGABLES, 1)],
        "plazo_dias": PLAZO_DIAS,
        "penalidades": PENALIDADES,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Escritos {PDF_EJEMPLO.name} y {RESPALDO_JSON.name}.")


if __name__ == "__main__":
    main()
