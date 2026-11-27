"""Documentos sintéticos de los postores del caso de laboratorio (Fase 3).

Genera PDFs con metadatos controlados para que la revisión documental tenga qué detectar:
- Tecnolab: cotización y certificado correctos.
- Kallpa: una partida mal multiplicada, el monto en letras no coincide, menciona el RUC de
  Servimax (copia y pega), una constancia vencida y experiencia anterior a su creación.
- Servimax: creada por el mismo autor que Kallpa 4 minutos después (cotizaciones gemelas),
  con párrafos idénticos y la misma falta de ortografía.

Uso:  python -m scripts.casos_documentos   (tras scripts.casos_evaluacion)
"""
import io
from datetime import datetime, timedelta, timezone

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.orm import Session

from conforme import auth, db
from conforme.documentos import repositorio
from conforme.modelos import Expediente, ExpedientePostor, Usuario
from conforme.proveedores import fuentes
from scripts.casos_evaluacion import LABORATORIO

_LIMA = timezone(timedelta(hours=-5))

_COMUNES = [
    "Nuestra empresa cuenta con amplia experiencia en el mantenimeinto de equipos de laboratorio para instituciones publicas y privadas.",
    "El servicio incluye la limpieza, ajuste y verificacion de cada equipo segun las recomendaciones del fabricante.",
    "La forma de pago sera al cien por ciento contra entrega de la conformidad del servicio por parte del area usuaria.",
]


def _pdf(lineas: list[str], *, autor: str, programa: str, creado: datetime, modificado: datetime | None = None) -> bytes:
    salida = io.BytesIO()
    lienzo = canvas.Canvas(salida, pagesize=A4, invariant=1)  # mismos bytes en cada generación
    y = 800
    for linea in lineas:
        if y < 60:
            lienzo.showPage()
            y = 800
        lienzo.setFont("Helvetica-Bold" if linea.isupper() else "Helvetica", 10)
        lienzo.drawString(50, y, linea)
        y -= 16
    lienzo.save()
    escritor = PdfWriter(clone_from=PdfReader(io.BytesIO(salida.getvalue())))
    formato = lambda f: f.strftime("D:%Y%m%d%H%M%S-05'00'")
    escritor.add_metadata({"/Author": autor, "/Creator": programa, "/Producer": programa,
                           "/CreationDate": formato(creado), "/ModDate": formato(modificado or creado)})
    final = io.BytesIO()
    escritor.write(final)
    return final.getvalue()


def _cotizacion(razon, ruc, numero, cuerpo, partidas, subtotal, igv, total, letras):
    lineas = [f"COTIZACION {numero}", razon, f"RUC: {ruc}", "",
              "Senores: Universidad Nacional de Trujillo - Unidad de Abastecimiento",
              f"Referencia: {LABORATORIO}", ""]
    lineas += cuerpo + ["", "DETALLE DE LA PROPUESTA ECONOMICA", "Descripcion   Cant.   P. unit.   Subtotal"]
    lineas += [f"{i}. {d}   {c}   {pu}   {st}" for i, (d, c, pu, st) in enumerate(partidas, start=1)]
    lineas += ["", f"Subtotal   {subtotal}", f"IGV 18%   {igv}", f"Total   {total}", f"SON: {letras} SOLES", "",
               "Validez de la oferta: 30 dias calendario."]
    return lineas


def documentos() -> dict[str, list[tuple[str, str, bytes]]]:
    """RUC → [(tipo, nombre, contenido)]."""
    base = datetime(2026, 11, 21, 16, 2, tzinfo=_LIMA)
    tecnolab = _cotizacion(
        "TECNOLAB SERVICIOS INTEGRALES S.A.C.", fuentes.RUC_TECNOLAB, "COT-TL-2026-118",
        ["Proponemos ejecutar el plan de mantenimiento con su cronograma de visitas a cada laboratorio.",
         "Al terminar entregaremos un informe tecnico de mantenimiento por cada equipo intervenido.",
         "Los certificados de calibracion vigentes se emiten con patrones trazables al INACAL.",
         "Contamos con dos ingenieros electronicos y un tecnico metrologo asignados al servicio."],
        [("Mantenimiento preventivo de espectrofotometro", "2", "3,850.00", "7,700.00"),
         ("Mantenimiento de balanzas analiticas", "6", "850.00", "5,100.00"),
         ("Calibracion de pHmetros y conductimetros", "8", "640.00", "5,120.00"),
         ("Mantenimiento de campana extractora", "2", "1,950.00", "3,900.00"),
         ("Informe tecnico y certificados", "1", "1,357.97", "1,357.97")],
        "23,177.97", "4,172.03", "27,350.00", "VEINTISIETE MIL TRESCIENTOS CINCUENTA CON 00/100")
    kallpa = _cotizacion(
        "INVERSIONES KALLPA ANDINA E.I.R.L.", fuentes.RUC_KALLPA, "PROF-0007",
        _COMUNES + ["Presentamos el plan de mantenimiento para los equipos del laboratorio.",
                    f"Datos de la empresa para la orden: RUC: {fuentes.RUC_SERVIMAX}"],
        [("Mantenimiento preventivo de equipos", "10", "1,200.00", "12,500.00"),
         ("Calibracion de instrumentos", "8", "545.55", "4,364.41")],
        "16,864.41", "3,035.59", "19,900.00", "DIECINUEVE MIL NOVECIENTOS NOVENTA CON 00/100")
    servimax = _cotizacion(
        "GRUPO SERVIMAX DEL NORTE S.A.C.", fuentes.RUC_SERVIMAX, "SMX-COT-552",
        _COMUNES + ["Presentamos el plan de mantenimiento y cronograma de trabajo.",
                    "Se entregara un informe tecnico de mantenimiento por cada equipo."],
        [("Mantenimiento preventivo de equipos", "10", "1,650.00", "16,500.00"),
         ("Calibracion de instrumentos", "8", "1,250.00", "10,000.00"),
         ("Informe tecnico", "1", "1,974.58", "1,974.58")],
        "28,474.58", "5,125.42", "33,600.00", "TREINTA Y TRES MIL SEISCIENTOS CON 00/100")
    return {
        fuentes.RUC_TECNOLAB: [
            ("cotizacion", "cotizacion-tecnolab.pdf",
             _pdf(tecnolab, autor="Carlos Rios", programa="Microsoft Word 2019", creado=base - timedelta(days=3, hours=6))),
            ("certificado", "certificado-experiencia-tecnolab.pdf", _pdf(
                ["CERTIFICADO DE EXPERIENCIA", "Hospital Belen de Trujillo certifica que TECNOLAB SERVICIOS INTEGRALES S.A.C.",
                 f"con RUC {fuentes.RUC_TECNOLAB} ejecuto el mantenimiento de equipos de laboratorio",
                 "entre el 15/03/2019 y el 30/06/2019 a entera satisfaccion."],
                autor="Hospital Belen", programa="Adobe Acrobat", creado=datetime(2019, 7, 5, 10, 0, tzinfo=_LIMA))),
        ],
        fuentes.RUC_KALLPA: [
            ("cotizacion", "proforma-kallpa.pdf", _pdf(kallpa, autor="PC-OFICINA", programa="Microsoft Word 2016", creado=base)),
            ("declaracion_jurada", "constancia-rnp-kallpa.pdf", _pdf(
                ["CONSTANCIA DE INSCRIPCION EN EL RNP", "INVERSIONES KALLPA ANDINA E.I.R.L.",
                 f"RUC: {fuentes.RUC_KALLPA}", "Capitulo: servicios", "Vigente hasta el 30/06/2026"],
                autor="PC-OFICINA", programa="Microsoft Word 2016", creado=base + timedelta(minutes=9))),
            ("certificado", "certificado-experiencia-kallpa.pdf", _pdf(
                ["CERTIFICADO DE EXPERIENCIA", "Se certifica que INVERSIONES KALLPA ANDINA E.I.R.L.",
                 "presto el servicio de mantenimiento de equipos del 10/02/2024 al 20/04/2024."],
                autor="PC-OFICINA", programa="Microsoft Word 2016", creado=base + timedelta(minutes=12))),
        ],
        fuentes.RUC_SERVIMAX: [
            ("cotizacion", "cotizacion-servimax.pdf",
             _pdf(servimax, autor="PC-OFICINA", programa="Microsoft Word 2016", creado=base + timedelta(minutes=4))),
        ],
    }


def sembrar_documentos(sesion: Session, expediente_id: int) -> int:
    usuario_id = sesion.scalar(select(Usuario.id).where(Usuario.username == "dec1"))
    dec1 = auth.actor_por_id(sesion, usuario_id)
    postores = {p.ruc: p.id for p in sesion.scalars(select(ExpedientePostor)
                                                    .where(ExpedientePostor.expediente_id == expediente_id))}
    total = 0
    for ruc, docs in documentos().items():
        if ruc not in postores:
            continue
        for tipo, nombre, contenido in docs:
            repositorio.subir_documento(sesion, dec1, expediente_id, postores[ruc], tipo=tipo, nombre_archivo=nombre,
                                        mime="application/pdf", contenido=contenido)
            total += 1
    return total


if __name__ == "__main__":
    with db.sesion() as s:
        expediente = s.scalar(select(Expediente).where(Expediente.descripcion == LABORATORIO)
                              .order_by(Expediente.id.desc()).limit(1))
        if expediente is None:
            raise SystemExit("No está el caso de laboratorio. Ejecuta antes: python -m scripts.casos_evaluacion")
        codigo = expediente.codigo
        cargados = sembrar_documentos(s, expediente.id)
    print(f"{cargados} documentos cargados en {codigo}.")
