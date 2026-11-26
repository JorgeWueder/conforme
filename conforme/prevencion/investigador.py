"""Recuperación acotada de fuentes públicas y análisis trazable con eve."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from html.parser import HTMLParser
from io import BytesIO
from time import monotonic
from urllib.parse import urljoin, urlsplit
import json
import logging
import re

import httpx
from pydantic import BaseModel, Field, ValidationError
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from conforme import config
from conforme.prevencion import demo, simulador

log = logging.getLogger(__name__)
_MAX_BYTES = 5 * 1024 * 1024
_DOMINIOS_BUSQUEDA = ("gob.pe", "contraloria.gob.pe", "pj.gob.pe", "congreso.gob.pe")


class InvestigadorNoDisponible(Exception):
    pass


class Afirmacion(BaseModel):
    afirmacion: str = Field(min_length=5, max_length=700)
    documento: str = Field(min_length=1, max_length=60)
    pagina: int = Field(ge=1, le=1000)
    extracto: str = Field(min_length=12, max_length=400)
    estado: str = Field(pattern=r"^(corroborado|por_verificar)$")


class Borrador(BaseModel):
    afirmaciones: list[Afirmacion] = Field(max_length=8)
    pendientes: list[str] = Field(max_length=8)


def url_oficial(url: str) -> bool:
    try:
        partes = urlsplit(url)
        dominio = partes.hostname or ""
        return (
            partes.scheme == "https" and not partes.username and not partes.password
            and partes.port in (443, None) and dominio.endswith(".gob.pe")
        )
    except ValueError:
        return False


def _descargar(url):
    with httpx.Client(timeout=6, follow_redirects=False) as cliente:
        limite = monotonic() + 10
        for _ in range(4):
            if not url_oficial(url):
                raise ValueError("El destino no pertenece a una fuente oficial admitida.")
            with cliente.stream("GET", url) as respuesta:
                if respuesta.is_redirect:
                    url = urljoin(url, respuesta.headers.get("location", ""))
                    continue
                respuesta.raise_for_status()
                contenido = bytearray()
                for bloque in respuesta.iter_bytes():
                    if len(contenido) + len(bloque) > _MAX_BYTES or monotonic() > limite:
                        raise ValueError("El documento superó el límite de lectura.")
                    contenido.extend(bloque)
                return url, bytes(contenido)
    raise ValueError("Demasiadas redirecciones.")


class _EnlacesPdf(HTMLParser):
    def __init__(self):
        super().__init__()
        self.enlaces = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href") or ""
            if urlsplit(href).path.lower().endswith(".pdf"):
                self.enlaces.append(href)


def _documento(url, title, ruc, acto):
    try:
        url, contenido = _descargar(url)
        if not contenido.startswith(b"%PDF-"):
            enlaces = _EnlacesPdf()
            enlaces.feed(contenido.decode("utf-8", errors="replace"))
            pdf = next((destino for enlace in enlaces.enlaces if url_oficial(destino := urljoin(url, enlace))), None)
            if not pdf:
                return None
            url, contenido = _descargar(pdf)
            if not contenido.startswith(b"%PDF-"):
                return None
        digest = sha256(contenido).hexdigest()
        lector = PdfReader(BytesIO(contenido))
        paginas = []
        for i, pagina in enumerate(lector.pages[:24], 1):
            texto = " ".join((pagina.extract_text() or "").split())
            if texto:
                texto = re.sub(r"(?i)(DNI\s*[:º.°-]*\s*)[0-9]{8}\b", r"\1[omitido]", texto)
                ruc_en_pagina = re.search(rf"(?<!\d){ruc}(?!\d)", texto)
                acto_en_pagina = acto and acto.casefold() in texto.casefold()
                prioridad = 2 * bool(ruc_en_pagina) + bool(acto_en_pagina)
                ancla = ruc_en_pagina.start() if ruc_en_pagina else (
                    texto.casefold().find(acto.casefold()) if acto_en_pagina else 0
                )
                inicio = max(0, ancla - 1100)
                paginas.append((prioridad, i, texto[inicio:inicio + 4200]))
        seleccion = sorted(paginas, key=lambda p: (-p[0], p[1]))[:4]
        if not seleccion or seleccion[0][0] == 0:
            return None
        return dict(id=digest[:18], titulo=title[:180], url=url, sha256=digest,
                    paginas=[dict(numero=i, texto=t[:4200]) for _, i, t in seleccion])
    except (httpx.HTTPError, OSError, PdfReadError, ValueError):
        log.info("Fuente documental no disponible para el investigador", exc_info=False)
        return None


def _buscar(ruc, acto):
    clave = config.leer("PREVENCION_BRAVE_API_KEY")
    if not clave:
        return []
    dominios = " OR ".join(f"site:{dominio}" for dominio in _DOMINIOS_BUSQUEDA)
    consultas = [f'"{ruc}"']
    if acto:
        acto_publico = re.sub(r"[^\w .:/-]", "", acto)
        consultas[:0] = [f'"{acto_publico}" (suspensión OR rectificación OR recurso OR archivo)', f'"{acto_publico}"']

    def documentos(consulta):
        try:
            respuesta = httpx.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": f"{consulta} ({dominios})", "count": 5, "search_lang": "es"},
                headers={"X-Subscription-Token": clave}, timeout=8,
            )
            respuesta.raise_for_status()
            resultados = respuesta.json().get("web", {}).get("results", [])
            return [(fila["url"], fila.get("title", "Documento oficial")) for fila in resultados
                    if isinstance(fila.get("url"), str) and url_oficial(fila["url"])][:2]
        except (httpx.HTTPError, ValueError):
            log.info("Búsqueda documental pública no disponible")
            return []

    with ThreadPoolExecutor(max_workers=3) as grupo:
        return [item for resultados in grupo.map(documentos, consultas) for item in resultados]


def recuperar(ruc, acto, urls):
    destinos = [(url, "Acto enlazado en la edición") for url in urls if url_oficial(url)]
    destinos.extend(_buscar(ruc, acto))
    unicos = list(dict(destinos).items())[:5]
    with ThreadPoolExecutor(max_workers=4) as grupo:
        resultados = grupo.map(lambda destino: _documento(*destino, ruc, acto), unicos)
        return list({doc["id"]: doc for doc in resultados if doc}.values())


def _resultado_eve(lineas, entrega, limite):
    resultado = None
    for linea in lineas:
        if monotonic() > limite:
            break
        if not linea:
            continue
        evento = json.loads(linea)
        for hecho in evento.get("facts", []):
            tipo, datos = hecho.get("type"), hecho.get("data", {})
            if tipo == "content.completed" and datos.get("kind") == "result":
                resultado = datos.get("value")
            if tipo == "delivery.settled" and datos.get("deliveryId") == entrega:
                if datos.get("outcome") == "handled":
                    return Borrador.model_validate(resultado)
                raise InvestigadorNoDisponible
            if tipo in ("session.ended", "turn.paused") or (
                tipo == "turn.settled" and datos.get("outcome") != "completed"
            ):
                raise InvestigadorNoDisponible
        if evento.get("$eve") == "stream.ended":
            break
    raise InvestigadorNoDisponible


def _llamar_eve(ruc, acto, fecha, documentos, operacion):
    base = config.leer("CONFORME_EVE_URL")
    token = config.leer("CONFORME_EVE_TOKEN")
    if not base or not token:
        raise InvestigadorNoDisponible
    api = base.rstrip("/") + "/eve/v1/session"
    cuerpo = {
        "message": "Revisa la evidencia para este candidato. Cita únicamente páginas incluidas en el contexto.",
        "clientContext": dict(ruc=ruc, acto=acto, fecha=fecha, documentos=documentos),
        "outputSchema": Borrador.model_json_schema(),
        "operationId": operacion,
    }
    with httpx.Client(timeout=httpx.Timeout(45, connect=5), headers={"Authorization": "Bearer " + token}) as cliente:
        respuesta = cliente.post(api, json=cuerpo)
        respuesta.raise_for_status()
        recibo = respuesta.json()
        session_url = f"{api}/{recibo['sessionId']}"
        try:
            limite = monotonic() + 50
            with cliente.stream("GET", session_url + "/stream") as eventos:
                eventos.raise_for_status()
                return _resultado_eve(eventos.iter_lines(), recibo["deliveryId"], limite)
        finally:
            try:
                cliente.post(session_url + "/end", timeout=3)
            except httpx.HTTPError:
                log.info("La sesión eve concluirá por expiración")


def validar_citas(borrador, documentos, ruc, acto):
    por_id = {doc["id"]: doc for doc in documentos}
    afirmaciones = []
    for cita in borrador.afirmaciones:
        doc = por_id.get(cita.documento)
        if not doc:
            continue
        texto = next((p["texto"] for p in doc["paginas"] if p["numero"] == cita.pagina), "")
        extracto = " ".join(cita.extracto.split())
        if extracto not in " ".join(texto.split()):
            continue
        identidad = any(re.search(rf"(?<!\d){ruc}(?!\d)", p["texto"]) for p in doc["paginas"])
        if acto:
            identidad |= any(acto.casefold() in p["texto"].casefold() for p in doc["paginas"])
        afirmaciones.append(dict(
            afirmacion=cita.afirmacion, estado=cita.estado if identidad else "por_verificar",
            titulo=doc["titulo"], url=doc.get("url"), pagina=cita.pagina,
            extracto=extracto, sha256=doc.get("sha256"),
        ))
    pendientes = [p[:500] for p in borrador.pendientes]
    if len(afirmaciones) != len(borrador.afirmaciones):
        pendientes.append("Se descartaron afirmaciones sin un extracto verificable en la página citada.")
    return afirmaciones, pendientes


def investigar(ruc, acto, fecha, urls, *, sintetico, operacion, simulado=False, nombre=None):
    if not sintetico and not simulado and not ruc.startswith("20"):
        return dict(modo="sin_documentos", afirmaciones=[],
                    pendientes=["Registra la comprobación de esta persona en el canal institucional aplicable."])
    if sintetico:
        documentos = demo.documentos(ruc, acto)
    elif simulado:
        documentos = simulador.documentos_simulados(ruc, acto, nombre)
    else:
        documentos = recuperar(ruc, acto, urls)
    if not documentos:
        return dict(modo="sin_documentos", afirmaciones=[],
                    pendientes=["Consulta el acto en la fuente oficial o incorpora su referencia a los hallazgos."])
    modo = "eve"
    try:
        borrador = _llamar_eve(ruc, acto, fecha, documentos, operacion)
    except (InvestigadorNoDisponible, httpx.HTTPError, ValidationError, ValueError, KeyError) as error:
        if not sintetico and not simulado:
            raise InvestigadorNoDisponible from error
        modo = "ejemplo" if sintetico else "simulacion"
        nota_pendiente = (
            "Ejemplo documental ficticio. Confirma el estado del acto por el canal oficial."
            if sintetico
            else "Resultado de verificación documental simulada. Contrasta el acto en la fuente oficial."
        )
        borrador = Borrador(afirmaciones=[
            Afirmacion(afirmacion=pagina["texto"], documento=doc["id"], pagina=pagina["numero"],
                       extracto=pagina["texto"], estado="por_verificar")
            for doc in documentos for pagina in doc["paginas"]
        ], pendientes=[nota_pendiente])
    afirmaciones, pendientes = validar_citas(borrador, documentos, ruc, acto)
    return dict(modo=modo, afirmaciones=afirmaciones, pendientes=pendientes)
