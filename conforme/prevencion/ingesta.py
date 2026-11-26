"""Conectores de ediciones oficiales y normalización al índice precontractual."""
from codecs import getincrementaldecoder
from contextlib import contextmanager
from datetime import date, datetime
from hashlib import sha256
from io import TextIOWrapper
from itertools import chain, islice
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from zipfile import ZipFile, is_zipfile
import csv

import httpx
from openpyxl import load_workbook
from sqlalchemy import insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from conforme.modelos import PrevencionEdicion as Edicion, PrevencionRegistro as Registro
from conforme.prevencion.evaluacion import texto_normalizado
from conforme.prevencion.fuentes import FUENTES
from conforme.prevencion.investigador import url_oficial

_MAX_DESCARGA = 550 * 1024 * 1024
_MAX_PADRON = 7 * 1024 ** 3
_DOMINIOS = {
    "www2.sunat.gob.pe", "www.sunat.gob.pe", "osce-gob-pe.atlassian.net",
    "api.media.atlassian.com", "conosce.oece.gob.pe",
}

_COMUNES = {
    "ruc": ("ruc", "ruc_dni", "ruc_contratista", "ruc_proveedor", "nro_ruc_proveedor", "numero_ruc_proveedor",
            "nro_documento_proveedor", "nro_documento", "numero_documento_proveedor", "proveedor_ruc"),
    "nombre": ("nombre_razonodenominacionsocial", "razon_social", "nombre_razon_social"),
    "acto": ("numero_resolucion", "nro_resolucion"),
    "inicio": ("fecha_inicio", "fecha_inicio_vigencia"),
    "fin": ("fecha_fin",),
    "motivo": ("de_motivo_infraccion", "descripcion_motivo", "organo_jurisdiccional", "tipo_penalidad"),
    "importe": ("monto",),
    "url_acto": ("url_resolucion", "enlace_resolucion", "url_acto"),
    "corte": ("fecha_corte",),
}
_ORDEN = {
    "ruc": _COMUNES["ruc"],
    "entidad_ruc": ("entidad_ruc", "ruc_entidad", "ruc_entidad_contratante", "numero_ruc_entidad",
                    "nro_ruc_entidad", "nro_documento_entidad", "ruc_de_la_entidad"),
    "acto": ("acto", "numero_orden", "nro_orden", "nro_orden_compra_servicio", "numero_orden_compra_servicio",
             "nro_orden_de_compra_o_servicio", "nro_orden_de_compra_y_o_servicio", "nro_orden_compra_y_o_servicio",
             "numero_orden_de_compra_y_o_servicio", "codigo_orden", "codigo_orden_compra_servicio"),
    "fecha": ("fecha", "fecha_orden", "fecha_emision", "fecha_emision_orden", "fecha_emision_de_la_orden",
              "fecha_de_emision", "fecha_de_emision_de_la_orden", "fecha_de_orden"),
    "objeto": ("objeto", "descripcion", "objeto_orden", "descripcion_orden", "descripcion_de_la_orden",
               "descripcion_del_objeto", "descripcion_de_la_contratacion", "descripcion_objeto", "objeto_de_contratacion"),
    "importe": ("importe", "monto", "monto_total", "monto_de_la_orden", "monto_total_de_la_orden", "monto_orden"),
    "moneda": ("moneda", "tipo_moneda", "moneda_orden"),
    "estado": ("estado", "estado_orden", "estado_de_la_orden"),
}
_PENALIDAD = _COMUNES | {
    "acto": ("id_contrato", "numero_contrato"),
    "fecha": ("fecha_penalidad",),
    "objeto": ("objeto_contrato",),
}
_VINCULO = {"ruc": ("ruc",), "corte": ("fecha_corte",), "tipo": ("tipo_conf_juridica",)}
_REQUERIDOS = {
    "tcp": {"ruc", "acto", "inicio"},
    "multa": {"ruc", "acto"},
    "judicial": {"ruc", "acto", "inicio"},
    "penalidad": {"ruc", "acto", "fecha"},
    "vinculo": {"ruc", "tipo"},
    "orden": {"ruc", "entidad_ruc", "acto", "fecha", "objeto"},
}
_FECHAS = {"inicio", "fin", "fecha", "corte"}


def descargar(url: str, archivo: Path) -> str:
    with httpx.Client(timeout=httpx.Timeout(45, connect=10), follow_redirects=False) as cliente:
        for _ in range(5):
            partes = urlsplit(url)
            if (partes.scheme != "https" or partes.hostname not in _DOMINIOS or
                    partes.port not in (None, 443) or partes.username or partes.password):
                raise ValueError("La descarga requiere una URL oficial de SUNAT, OECE o CONOSCE.")
            with cliente.stream("GET", url) as respuesta:
                if respuesta.is_redirect:
                    url = urljoin(url, respuesta.headers.get("location", ""))
                    continue
                respuesta.raise_for_status()
                bytes_leidos = 0
                with archivo.open("wb") as salida:
                    for bloque in respuesta.iter_bytes(chunk_size=1024 * 1024):
                        bytes_leidos += len(bloque)
                        if bytes_leidos > _MAX_DESCARGA:
                            raise ValueError("El archivo excede el tamaño permitido. Descárgalo e impórtalo localmente.")
                        salida.write(bloque)
                return respuesta.headers.get("content-type", "")
    raise ValueError("Demasiadas redirecciones en la fuente.")


def _cadena(dato):
    if isinstance(dato, float) and dato.is_integer():
        return str(int(dato))
    return str(dato).strip() if dato is not None else ""


def _fecha(dato) -> str | None:
    if isinstance(dato, datetime):
        return dato.date().isoformat()
    if isinstance(dato, date):
        return dato.isoformat()
    texto = _cadena(dato)
    if not texto:
        return None
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y%m%d", "%Y-%m-%d %H:%M:%S",
                    "%d/%m/%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(texto, formato).date().isoformat()
        except ValueError:
            continue
    return None


def _ruc(dato):
    valor = _cadena(dato)
    return valor if len(valor) == 11 and valor.isascii() and valor.isdigit() else None


def _csv(datos):
    muestra = datos.readline()
    datos.seek(0)
    try:
        formato = csv.Sniffer().sniff(muestra, delimiters="|;,\t")
    except csv.Error as error:
        raise ValueError("No se reconoció el separador del archivo.") from error
    return csv.reader(datos, formato)


@contextmanager
def _filas(archivo, fuente, codificacion):
    if fuente != "sunat" and is_zipfile(archivo):
        # El archivo de publicación de CONOSCE puede ser un libro XLSX.
        with archivo.open("rb") as entrada:
            libro = load_workbook(entrada, read_only=True, data_only=True)
            try:
                yield ((n, fila) for n, fila in enumerate(libro.active.values, 1))
            finally:
                libro.close()
        return
    if codificacion is None:
        with archivo.open("rb") as binario:
            muestra = binario.read(64 * 1024)
        try:
            getincrementaldecoder("utf-8-sig")().decode(muestra)
            codificacion = "utf-8-sig"
        except UnicodeDecodeError:
            codificacion = "cp1252"
    with archivo.open(encoding=codificacion, newline="") as entrada:
        filas = _csv(entrada)
        def numerar():
            inicio = 1
            for fila in filas:
                yield inicio, fila
                inicio = filas.line_num + 1
        yield numerar()


def _padron(archivo):
    with ZipFile(archivo) as zip_:
        miembros = [m for m in zip_.infolist() if m.filename.lower().endswith(".txt") and not m.is_dir()]
        if len(miembros) != 1 or miembros[0].file_size > _MAX_PADRON:
            raise ValueError("El ZIP debe contener un único TXT del padrón reducido.")
        with TextIOWrapper(zip_.open(miembros[0]), encoding="latin-1") as texto:
            cabecera = next(texto, "").lstrip("\ufeff").upper()
            if not cabecera.startswith("RUC|") or "ESTADO" not in cabecera or "CONDICI" not in cabecera:
                raise ValueError("El padrón reducido tiene una cabecera desconocida.")
            for numero, linea in enumerate(texto, 2):
                partes = linea.rstrip("\r\n").split("|", 4)
                if len(partes) < 4 or not (ruc := _ruc(partes[0])) or not ruc.startswith("20"):
                    continue
                yield numero, ruc, dict(zip(("nombre", "estado", "condicion"), partes[1:4]))


def _columnas(encabezado, fuente, asignacion):
    indices = {texto_normalizado(_cadena(v)).replace(" ", "_"): i for i, v in enumerate(encabezado) if v}
    aliases = {"orden": _ORDEN, "penalidad": _PENALIDAD, "vinculo": _VINCULO}.get(fuente, _COMUNES)
    columnas = {}
    for campo, opciones in aliases.items():
        nombres = (asignacion[campo],) if campo in asignacion else opciones
        for nombre in nombres:
            indice = indices.get(texto_normalizado(nombre.replace("_", " ")).replace(" ", "_"))
            if indice is not None:
                columnas[campo] = indice
                break
    faltan = _REQUERIDOS[fuente] - columnas.keys()
    if faltan:
        raise ValueError(f"Columnas requeridas sin reconocer en {fuente}: {', '.join(sorted(faltan))}.")
    return columnas


def registros(archivo, fuente, codificacion=None, asignacion=None):
    if fuente == "sunat":
        yield from _padron(archivo)
        return
    with _filas(archivo, fuente, codificacion) as filas:
        encabezado = next(filas, None)
        if encabezado is None:
            raise ValueError("La edición está vacía.")
        columnas = _columnas(encabezado[1], fuente, asignacion or {})
        for numero, fila in filas:
            valores = {campo: (fila[i] if i < len(fila) else None) for campo, i in columnas.items()}
            ruc = _ruc(valores.pop("ruc"))
            if not ruc or not ruc.startswith("20"):
                continue
            datos = {campo: _fecha(dato) if campo in _FECHAS else _cadena(dato)[:1000]
                     for campo, dato in valores.items() if _cadena(dato)}
            if fuente == "orden" and (not _ruc(datos.get("entidad_ruc")) or not all(datos.get(c) for c in ("fecha", "acto", "objeto"))):
                continue
            if fuente in ("tcp", "judicial", "multa", "penalidad") and not datos.get("acto"):
                continue
            if "url_acto" in datos and not url_oficial(datos["url_acto"]):
                del datos["url_acto"]
            yield numero, ruc, datos


def _corte_sin_empresas(archivo, fuente, codificacion):
    if fuente not in ("tcp", "multa", "judicial", "vinculo"):
        return None
    with _filas(archivo, fuente, codificacion) as filas:
        encabezado = next(filas, None)
        if not encabezado:
            return None
        indice = _columnas(encabezado[1], fuente, {}).get("corte")
        if indice is None:
            return None
        return next((fecha for _, fila in filas if indice < len(fila) and (fecha := _fecha(fila[indice]))), None)


def publicar(sesion, archivo, fuente, corte, alcance, origen, codificacion=None, asignacion=None):
    huella = sha256()
    with archivo.open("rb") as entrada:
        for bloque in iter(lambda: entrada.read(1024 * 1024), b""):
            huella.update(bloque)
    firma = huella.hexdigest()
    with _abrir_registros(archivo, fuente, codificacion, asignacion) as filas:
        primero = next(filas, None)
        corte_del_archivo = (
            primero[2].get("corte") if primero else _corte_sin_empresas(archivo, fuente, codificacion)
        )
        if not corte and not corte_del_archivo:
            raise ValueError("Indica la fecha de publicación declarada por la fuente con --corte.")
        corte = corte or date.fromisoformat(corte_del_archivo)
        if corte > date.today():
            raise ValueError("El corte de la fuente debe ser hoy o anterior.")
        if corte_del_archivo and corte_del_archivo != corte.isoformat():
            raise ValueError("La fecha de corte indicada difiere de la publicada en el archivo.")
        manifiesto = dict(origen=origen, archivo=archivo.name, cobertura="RUC de personas jurídicas")
        comando = (pg_insert(Edicion).values(
            fuente=fuente, fecha_corte=corte, descargado_en=datetime.now().astimezone(), sha256=firma,
            alcance=alcance, manifiesto=manifiesto,
        ).on_conflict_do_nothing(index_elements=["fuente", "fecha_corte", "sha256", "alcance"])
            .returning(Edicion.id))
        edicion_id = sesion.scalar(comando)
        if edicion_id is None:
            previo = sesion.scalar(select(Edicion.id).where(
                Edicion.fuente == fuente, Edicion.fecha_corte == corte, Edicion.sha256 == firma,
                Edicion.alcance == alcance,
            ))
            return previo, None
        total = _insertar(sesion, edicion_id, corte, primero, filas)
        if total == 0:
            manifiesto["cobertura"] += " · sin filas de empresas en la edición"
        manifiesto["filas"] = total
        sesion.get(Edicion, edicion_id).manifiesto = manifiesto
        return edicion_id, total


@contextmanager
def _abrir_registros(*args):
    generador = registros(*args)
    try:
        yield generador
    finally:
        generador.close()


def _insertar(sesion, edicion_id, corte, primero, filas):
    datos = chain((primero,), filas) if primero else filas
    total = 0
    while bloque := list(islice(datos, 2000)):
        carga = []
        for numero, ruc, campos in bloque:
            fecha_publicacion = campos.pop("corte", None)
            if fecha_publicacion and fecha_publicacion != corte.isoformat():
                raise ValueError("La edición contiene fechas de corte distintas.")
            carga.append(dict(edicion_id=edicion_id, fila=numero, ruc=ruc, datos=campos))
        sesion.execute(insert(Registro), carga)
        total += len(carga)
    return total
