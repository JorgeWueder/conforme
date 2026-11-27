"""Lectura de documentos: texto, metadatos del archivo y partidas de un presupuesto.

Admite PDF (pypdf), Word .docx y Excel .xlsx (sin dependencias: son ZIP con XML, salvo
Excel, que usa openpyxl) y CSV. No ejecuta macros ni contenido activo.
"""
import csv
import io
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree

from pypdf import PdfReader
from pypdf.errors import PyPdfError

MIMES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "text/csv": "csv",
}
EXTENSIONES = {"pdf": "pdf", "docx": "docx", "xlsx": "xlsx", "csv": "csv"}


@dataclass
class Partida:
    descripcion: str
    cantidad: Decimal
    precio_unitario: Decimal
    subtotal: Decimal


@dataclass
class Lectura:
    formato: str
    texto: str = ""
    autor: str | None = None
    creador: str | None = None        # programa que creó el archivo
    productor: str | None = None
    ultimo_editor: str | None = None
    creado: datetime | None = None
    modificado: datetime | None = None
    partidas: list[Partida] = field(default_factory=list)
    totales: dict = field(default_factory=dict)   # subtotal, igv, total, letras
    aviso: str | None = None


def formato_de(nombre: str, mime: str | None) -> str | None:
    if mime in MIMES:
        return MIMES[mime]
    extension = (nombre or "").rsplit(".", 1)[-1].lower()
    return EXTENSIONES.get(extension)


def _numero(texto) -> Decimal | None:
    if texto is None:
        return None
    if isinstance(texto, (int, float, Decimal)):
        return Decimal(str(texto))
    limpio = re.sub(r"[^\d.,-]", "", str(texto))
    if not limpio:
        return None
    if "," in limpio and "." in limpio:
        limpio = limpio.replace(",", "")
    elif "," in limpio:
        limpio = limpio.replace(",", ".")
    try:
        return Decimal(limpio)
    except InvalidOperation:
        return None


def _fecha_pdf(valor) -> datetime | None:
    if isinstance(valor, datetime):
        return valor if valor.tzinfo else valor.replace(tzinfo=timezone.utc)
    if not valor:
        return None
    m = re.match(r"D?:?(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?(\d{2})?", str(valor))
    if not m:
        return None
    partes = [int(p) if p else 0 for p in m.groups()]
    try:
        return datetime(*partes, tzinfo=timezone.utc)
    except ValueError:
        return None


def _fecha_iso(valor: str | None) -> datetime | None:
    if not valor:
        return None
    try:
        fecha = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        return None
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)


# --- Partidas y totales a partir de texto ------------------------------------------------
_LINEA_PARTIDA = re.compile(
    r"^\s*(?:\d+[.)]\s+)?(?P<desc>[^\d\n].*?)\s+(?P<cant>\d+(?:[.,]\d+)?)\s+"
    r"(?:S/\s*)?(?P<pu>[\d,]+\.\d{2})\s+(?:S/\s*)?(?P<sub>[\d,]+\.\d{2})\s*$")
_TOTALES = {
    "subtotal": re.compile(r"^\s*(?:sub\s*-?total|valor\s+de\s+venta)\b.*?(?P<v>[\d,]+\.\d{2})\s*$", re.I),
    "igv": re.compile(r"^\s*igv\b.*?(?P<v>[\d,]+\.\d{2})\s*$", re.I),
    "total": re.compile(r"^\s*(?:precio\s+)?total\b.*?(?P<v>[\d,]+\.\d{2})\s*$", re.I),
}
_LETRAS = re.compile(r"\bson\s*:?\s*(?P<l>[a-záéíóúñ ,y]+?)\s+(?:con\s+)?(?P<c>\d{2})\s*/\s*100", re.I)


def partidas_de_texto(texto: str) -> tuple[list[Partida], dict]:
    partidas, totales = [], {}
    for linea in texto.splitlines():
        encontrado = False
        for clave, patron in _TOTALES.items():
            m = patron.match(linea)
            if m and clave not in totales:
                totales[clave] = _numero(m.group("v"))
                encontrado = True
                break
        if encontrado:
            continue
        m = _LINEA_PARTIDA.match(linea)
        if m:
            partidas.append(Partida(m.group("desc").strip(" .:-"), _numero(m.group("cant")),
                                    _numero(m.group("pu")), _numero(m.group("sub"))))
    m = _LETRAS.search(texto)
    if m:
        totales["letras"] = f"{m.group('l').strip()} con {m.group('c')}/100"
    return partidas, totales


def _partidas_de_filas(filas) -> list[Partida]:
    partidas = []
    for fila in filas:
        celdas = [c for c in fila if c not in (None, "")]
        if len(celdas) < 4:
            continue
        numeros = [_numero(c) for c in celdas[-3:]]
        if None in numeros:
            continue
        descripcion = " ".join(str(c) for c in celdas[:-3]).strip()
        if not descripcion or descripcion.replace(".", "").isdigit():
            continue
        partidas.append(Partida(descripcion, *numeros))
    return partidas


# --- Por formato ---------------------------------------------------------------------------

def _pdf(contenido: bytes) -> Lectura:
    lector = PdfReader(io.BytesIO(contenido))
    meta = lector.metadata or {}
    texto = "\n".join((pagina.extract_text() or "") for pagina in lector.pages[:30])
    partidas, totales = partidas_de_texto(texto)
    return Lectura("pdf", texto=texto, autor=meta.get("/Author"), creador=meta.get("/Creator"),
                   productor=meta.get("/Producer"), creado=_fecha_pdf(meta.get("/CreationDate")),
                   modificado=_fecha_pdf(meta.get("/ModDate")), partidas=partidas, totales=totales)


_NS = {"dc": "http://purl.org/dc/elements/1.1/", "dcterms": "http://purl.org/dc/terms/",
       "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
       "ep": "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"}


def _propiedades_office(zona: zipfile.ZipFile) -> dict:
    datos = {}
    if "docProps/core.xml" in zona.namelist():
        raiz = ElementTree.fromstring(zona.read("docProps/core.xml"))
        datos["autor"] = raiz.findtext("dc:creator", namespaces=_NS)
        datos["ultimo_editor"] = raiz.findtext("cp:lastModifiedBy", namespaces=_NS)
        datos["creado"] = _fecha_iso(raiz.findtext("dcterms:created", namespaces=_NS))
        datos["modificado"] = _fecha_iso(raiz.findtext("dcterms:modified", namespaces=_NS))
    if "docProps/app.xml" in zona.namelist():
        raiz = ElementTree.fromstring(zona.read("docProps/app.xml"))
        datos["creador"] = raiz.findtext("ep:Application", namespaces=_NS)
    return datos


def _docx(contenido: bytes) -> Lectura:
    with zipfile.ZipFile(io.BytesIO(contenido)) as zona:
        props = _propiedades_office(zona)
        xml = zona.read("word/document.xml").decode("utf-8", "ignore")
    xml = re.sub(r"</w:p>", "\n", xml)
    texto = re.sub(r"<[^>]+>", "", xml)
    partidas, totales = partidas_de_texto(texto)
    return Lectura("docx", texto=texto, partidas=partidas, totales=totales, **props)


def _xlsx(contenido: bytes) -> Lectura:
    from openpyxl import load_workbook
    with zipfile.ZipFile(io.BytesIO(contenido)) as zona:
        props = _propiedades_office(zona)
    libro = load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
    filas = [tuple(fila) for hoja in libro.worksheets[:3] for fila in hoja.iter_rows(values_only=True, max_row=500)]
    libro.close()
    texto = "\n".join("  ".join(str(c) for c in fila if c is not None) for fila in filas)
    _, totales = partidas_de_texto(texto)
    return Lectura("xlsx", texto=texto, partidas=_partidas_de_filas(filas), totales=totales, **props)


def _csv(contenido: bytes) -> Lectura:
    texto = contenido.decode("utf-8-sig", "ignore")
    muestra = texto[:2000]
    try:
        dialecto = csv.Sniffer().sniff(muestra, delimiters=",;\t")
    except csv.Error:
        dialecto = csv.excel
    filas = list(csv.reader(io.StringIO(texto), dialecto))
    _, totales = partidas_de_texto(texto)
    return Lectura("csv", texto=texto, partidas=_partidas_de_filas(filas), totales=totales)


def leer(nombre: str, mime: str | None, contenido: bytes) -> Lectura:
    formato = formato_de(nombre, mime)
    try:
        if formato == "pdf":
            return _pdf(contenido)
        if formato == "docx":
            return _docx(contenido)
        if formato == "xlsx":
            return _xlsx(contenido)
        if formato == "csv":
            return _csv(contenido)
    except (PyPdfError, zipfile.BadZipFile, KeyError, ElementTree.ParseError, ValueError, OSError):
        return Lectura(formato or "desconocido", aviso="No se pudo leer el archivo: puede estar dañado o protegido.")
    return Lectura("desconocido", aviso="Formato no admitido para lectura: solo se registra su huella.")
