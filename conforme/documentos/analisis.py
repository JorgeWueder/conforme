"""Los cinco análisis de la revisión documental. Funciones puras sobre documentos ya leídos.

1. Montos y Benford: cuadre aritmético (cantidad × precio, sumas, IGV, letras) y Ley de Benford.
2. Metadatos: autor, programa y fechas; cotizaciones «gemelas» y posibles adulteraciones.
3. Cruce entre postores: frases y textos idénticos entre propuestas de supuestos competidores.
4. Cumplimiento del TDR: cada entregable contra la propuesta (lectura asistida, simulada).
5. Vigencias y coherencia: RUC ajeno, documentos vencidos, experiencia anterior a la empresa,
   archivos reciclados de otros expedientes (SHA-256).
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from itertools import combinations

from conforme import normativa
from conforme.documentos import benford, letras
from conforme.documentos.lectura import Lectura
from conforme.proveedores.dimensiones import ALERTA, LIMPIO, REVISAR, palabras

BLOQUES = {
    "montos": "Montos y Benford",
    "metadatos": "Metadatos de los archivos",
    "similitud": "Cruce entre postores",
    "tdr": "Cumplimiento del TDR",
    "coherencia": "Vigencias y coherencia",
}
TIPOS = {
    "cotizacion": "Cotización", "presupuesto": "Presupuesto desagregado", "propuesta_tecnica": "Propuesta técnica",
    "declaracion_jurada": "Declaración jurada", "certificado": "Certificado", "otro": "Otro documento",
}
_ORDEN = {LIMPIO: 0, REVISAR: 1, ALERTA: 2}
TIPOS_PROPUESTA = ("cotizacion", "propuesta_tecnica", "presupuesto")   # lo que se contrasta con el TDR


@dataclass
class Documento:
    id: int
    postor_id: int
    postor: str
    ruc: str
    tipo: str
    nombre: str
    sha256: str
    lectura: Lectura


@dataclass
class Contexto:
    hoy: date
    entregables: list[str]
    inicio_actividades: dict[int, date] = field(default_factory=dict)   # postor_id → fecha
    descripcion: str = ""
    entidad: str = "Universidad Nacional de Trujillo Unidad de Abastecimiento"
    reciclados: dict[str, list[str]] = field(default_factory=dict)       # sha256 → dónde más aparece


def _h(nivel, que, por_que, accion, postor=None, documento=None):
    return {"nivel": nivel, "que": que, "por_que": por_que, "accion": accion, "postor": postor, "documento": documento}


def _bloque(clave, hallazgos, resumen_limpio, **detalle):
    estado = max((h["nivel"] for h in hallazgos), key=_ORDEN.get, default=LIMPIO)
    if hallazgos:
        principal = next(h for h in hallazgos if h["nivel"] == estado)
        resumen = principal["que"] + (f" (y {len(hallazgos) - 1} más)" if len(hallazgos) > 1 else "")
    else:
        resumen = resumen_limpio
    return {"clave": clave, "titulo": BLOQUES[clave], "estado": estado, "resumen": resumen,
            "hallazgos": hallazgos, "detalle": detalle}


def _soles(valor: Decimal) -> str:
    return f"S/ {valor:,.2f}"


# --- 1. Montos y Benford ------------------------------------------------------------------

def montos(documentos: list[Documento], ctx: Contexto) -> dict:
    hallazgos, por_documento, todos = [], [], []
    tolerancia = normativa.CUADRE_TOLERANCIA
    for doc in documentos:
        lec = doc.lectura
        if not lec.partidas and not lec.totales:
            continue
        revision = []
        for i, p in enumerate(lec.partidas, start=1):
            todos.append((f"{doc.postor}: {p.descripcion}", p.subtotal))
            esperado = (p.cantidad * p.precio_unitario).quantize(Decimal("0.01"))
            ok = abs(esperado - p.subtotal) <= tolerancia
            revision.append({"descripcion": p.descripcion, "cantidad": str(p.cantidad),
                             "precio_unitario": str(p.precio_unitario), "subtotal": str(p.subtotal),
                             "esperado": str(esperado), "cuadra": ok})
            if not ok:
                hallazgos.append(_h(ALERTA, f"Partida mal calculada en {doc.postor}: «{p.descripcion}»",
                                    f"{p.cantidad} × {_soles(p.precio_unitario)} = {_soles(esperado)}, "
                                    f"pero el documento dice {_soles(p.subtotal)}.",
                                    "Pide al postor que corrija y sustente el monto.", doc.postor, doc.nombre))
        t = lec.totales
        suma = sum((p.subtotal for p in lec.partidas), Decimal("0"))
        if lec.partidas and t.get("subtotal") is not None and abs(suma - t["subtotal"]) > tolerancia:
            hallazgos.append(_h(ALERTA, f"La suma de partidas de {doc.postor} no coincide con su subtotal",
                                f"Las partidas suman {_soles(suma)} y el subtotal declarado es {_soles(t['subtotal'])}.",
                                "Verifica qué monto es el correcto antes de comparar precios.", doc.postor, doc.nombre))
        if t.get("subtotal") is not None and t.get("igv") is not None:
            igv = (t["subtotal"] * normativa.IGV_TASA).quantize(Decimal("0.01"))
            if abs(igv - t["igv"]) > tolerancia:
                hallazgos.append(_h(REVISAR, f"El IGV de {doc.postor} no es el 18 % del subtotal",
                                    f"Debería ser {_soles(igv)}; el documento dice {_soles(t['igv'])}.",
                                    "Confirma si el postor está afecto al IGV o si hay un error.", doc.postor, doc.nombre))
        if t.get("total") is not None and t.get("subtotal") is not None and t.get("igv") is not None:
            if abs(t["subtotal"] + t["igv"] - t["total"]) > tolerancia:
                hallazgos.append(_h(ALERTA, f"El total de {doc.postor} no es subtotal + IGV",
                                    f"{_soles(t['subtotal'])} + {_soles(t['igv'])} ≠ {_soles(t['total'])}.",
                                    "Pide la corrección: el total es la base del precio ofertado.", doc.postor, doc.nombre))
        if t.get("total") is not None and t.get("letras"):
            if not letras.coincide(t["total"], t["letras"]):
                hallazgos.append(_h(ALERTA, f"El monto en letras de {doc.postor} no coincide con el número",
                                    f"En números dice {_soles(t['total'])}; en letras, «{t['letras']}» "
                                    f"(debería ser «{letras.monto_en_letras(t['total'])}»).",
                                    "Ante la discrepancia, pide aclaración por escrito al postor.", doc.postor, doc.nombre))
        por_documento.append({"postor": doc.postor, "documento": doc.nombre, "partidas": revision,
                              "totales": {k: str(v) for k, v in t.items()}})
    analisis_benford = benford.analizar(todos)
    if analisis_benford["nivel"] == "anomalia":
        hallazgos.append(_h(ALERTA, "Los montos de las partidas se alejan fuertemente de la Ley de Benford",
                            analisis_benford["lectura"], "Revisa las partidas señaladas en la gráfica."))
    elif analisis_benford["nivel"] == "marginal":
        hallazgos.append(_h(REVISAR, "Los montos de las partidas muestran una desviación marginal de Benford",
                            analisis_benford["lectura"], "Revisa las partidas señaladas en la gráfica."))
    limpio = ("Las partidas, el IGV y los montos en letras cuadran." if por_documento
              else "No hay presupuestos desagregados que cuadrar.")
    return _bloque("montos", hallazgos, limpio, documentos=por_documento, benford=analisis_benford)


# --- 2. Metadatos ---------------------------------------------------------------------------

def _hora(valor: datetime | None) -> str:
    return valor.strftime("%d/%m/%Y %H:%M") if valor else "—"


def metadatos(documentos: list[Documento], ctx: Contexto) -> dict:
    hallazgos, filas = [], []
    for doc in documentos:
        lec = doc.lectura
        filas.append({"postor": doc.postor, "documento": doc.nombre, "tipo": TIPOS.get(doc.tipo, doc.tipo),
                      "autor": lec.autor, "ultimo_editor": lec.ultimo_editor, "programa": lec.creador or lec.productor,
                      "creado": _hora(lec.creado), "modificado": _hora(lec.modificado)})
        if doc.tipo == "certificado" and lec.creado and lec.modificado and (lec.modificado - lec.creado).days > 30:
            hallazgos.append(_h(REVISAR, f"El certificado «{doc.nombre}» se modificó después de emitido",
                                f"Creado el {_hora(lec.creado)} y modificado el {_hora(lec.modificado)}.",
                                "Pide el original o verifica con quien lo emitió.", doc.postor, doc.nombre))
    vistos = set()
    for a, b in combinations(documentos, 2):
        if a.postor_id == b.postor_id:
            continue
        par = tuple(sorted((a.postor, b.postor)))
        motivos = []
        if a.lectura.autor and a.lectura.autor == b.lectura.autor:
            motivos.append(f"el mismo autor («{a.lectura.autor}»)")
        if a.lectura.ultimo_editor and a.lectura.ultimo_editor == b.lectura.ultimo_editor:
            motivos.append(f"el mismo último editor («{a.lectura.ultimo_editor}»)")
        if a.lectura.creado and b.lectura.creado:
            minutos = abs((a.lectura.creado - b.lectura.creado).total_seconds()) / 60
            if minutos <= normativa.DOCUMENTOS_GEMELOS_MINUTOS:
                motivos.append(f"creados con {minutos:.0f} minutos de diferencia")
        if motivos and par not in vistos:
            vistos.add(par)
            hallazgos.append(_h(ALERTA, f"Cotizaciones gemelas: {par[0]} y {par[1]}",
                                f"Documentos de postores que deberían competir tienen {' y '.join(motivos)}.",
                                "Trata estas cotizaciones como no independientes y documenta el hecho.",
                                f"{par[0]} / {par[1]}"))
    return _bloque("metadatos", hallazgos, "Los metadatos no muestran autores ni fechas en común entre postores.",
                   documentos=filas)


# --- 3. Similitud entre postores -------------------------------------------------------------

def _frases(texto: str) -> set[str]:
    frases = re.split(r"(?<=[.;:])\s+|\n+", texto or "")
    return {re.sub(r"\s+", " ", f).strip().lower() for f in frases if len(f.strip()) >= 45}


def _tejas(texto: str, n: int = 5) -> set[tuple]:
    tokens = re.findall(r"\w+", (texto or "").lower())
    return {tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)}


def _referencia(ctx: Contexto) -> set[str]:
    return palabras(" ".join([ctx.descripcion, ctx.entidad, "señores referencia"]))


def _sin_referencias(texto: str, referencia: set[str]) -> str:
    """Quita las líneas que solo citan el requerimiento o a la entidad: todas las cotizaciones
    las repiten y no indican que un mismo autor las redactó."""
    lineas = []
    for linea in (texto or "").splitlines():
        propias = palabras(linea)
        if propias and len(propias & referencia) / len(propias) >= 0.7:
            continue
        lineas.append(linea)
    return "\n".join(lineas)


def similitud(documentos: list[Documento], ctx: Contexto) -> dict:
    referencia = _referencia(ctx)
    por_postor: dict[int, list[Documento]] = {}
    for doc in documentos:
        if doc.lectura.texto.strip():
            por_postor.setdefault(doc.postor_id, []).append(doc)
    pares, hallazgos = [], []
    for (pa, da), (pb, db) in combinations(por_postor.items(), 2):
        texto_a = _sin_referencias("\n".join(d.lectura.texto for d in da), referencia)
        texto_b = _sin_referencias("\n".join(d.lectura.texto for d in db), referencia)
        ta, tb = _tejas(texto_a), _tejas(texto_b)
        indice = Decimal(len(ta & tb)) / Decimal(len(ta | tb)) if ta | tb else Decimal(0)
        comunes = sorted(_frases(texto_a) & _frases(texto_b), key=len, reverse=True)
        nombre_a, nombre_b = da[0].postor, db[0].postor
        pares.append({"postores": [nombre_a, nombre_b], "similitud": float(round(indice, 3)),
                      "frases_identicas": [f[:220] for f in comunes[:4]]})
        texto_similitud = f"{indice * 100:.0f} % del texto coincide y comparten {len(comunes)} frase(s) idéntica(s)."
        if indice >= normativa.SIMILITUD_ALERTA or len(comunes) >= 3:
            hallazgos.append(_h(ALERTA, f"Propuestas casi idénticas: {nombre_a} y {nombre_b}", texto_similitud,
                                "Son señales de que una misma persona redactó ambas: no las tomes como competencia real.",
                                f"{nombre_a} / {nombre_b}"))
        elif indice >= normativa.SIMILITUD_REVISAR or len(comunes) >= 1:
            hallazgos.append(_h(REVISAR, f"Textos parecidos entre {nombre_a} y {nombre_b}", texto_similitud,
                                "Compara las frases repetidas: pueden venir de una plantilla común o de un mismo autor.",
                                f"{nombre_a} / {nombre_b}"))
    limpio = ("Las propuestas de los postores no comparten textos." if len(por_postor) > 1
              else "Se necesita texto de al menos dos postores para cruzar.")
    return _bloque("similitud", hallazgos, limpio, pares=pares)


# --- 4. Cumplimiento del TDR ----------------------------------------------------------------

def tdr(documentos: list[Documento], ctx: Contexto) -> dict:
    por_postor: dict[int, list[Documento]] = {}
    for doc in documentos:
        if doc.tipo in TIPOS_PROPUESTA:
            por_postor.setdefault(doc.postor_id, []).append(doc)
    checklist, hallazgos = [], []
    if not ctx.entregables:
        return _bloque("tdr", [], "El expediente no tiene entregables registrados con qué contrastar.", checklist=[])
    for docs in por_postor.values():
        presentes = palabras(_sin_referencias("\n".join(d.lectura.texto for d in docs), _referencia(ctx)))
        items = []
        for entregable in ctx.entregables:
            terminos = palabras(entregable)
            cobertura = Decimal(len(terminos & presentes)) / Decimal(len(terminos)) if terminos else Decimal(1)
            if cobertura >= normativa.TDR_ACREDITADO:
                estado = "acreditado"
            elif cobertura >= normativa.TDR_INCOMPLETO:
                estado = "incompleto"
            else:
                estado = "no_cumple"
            items.append({"entregable": entregable, "estado": estado, "cobertura": float(round(cobertura, 2)),
                          "faltan": sorted(terminos - presentes)[:6]})
        postor = docs[0].postor
        checklist.append({"postor": postor, "items": items})
        no_cumple = [i["entregable"] for i in items if i["estado"] == "no_cumple"]
        incompletos = [i["entregable"] for i in items if i["estado"] == "incompleto"]
        if no_cumple:
            hallazgos.append(_h(ALERTA, f"La propuesta de {postor} no cubre {len(no_cumple)} entregable(s) del TDR",
                                "No menciona: " + "; ".join(no_cumple) + ".",
                                "Pide que acredite esos entregables o descarta la propuesta.", postor))
        elif incompletos:
            hallazgos.append(_h(REVISAR, f"La propuesta de {postor} cubre de forma incompleta {len(incompletos)} entregable(s)",
                                "Menciona solo en parte: " + "; ".join(incompletos) + ".",
                                "Revisa esos puntos en el documento antes de darlos por acreditados.", postor))
    return _bloque("tdr", hallazgos, "Todas las propuestas cubren los entregables del TDR.", checklist=checklist)


# --- 5. Vigencias, coherencia y huella ------------------------------------------------------

_RUC = re.compile(r"\b(?:10|15|16|17|20)\d{9}\b")
_VIGENCIA = re.compile(r"(?:vigente|v[aá]lid[oa]|vence|vencimiento)\D{0,25}?(\d{2})/(\d{2})/(\d{4})", re.I)
_FECHA = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")


def _fecha(d, m, a) -> date | None:
    try:
        return date(int(a), int(m), int(d))
    except ValueError:
        return None


def coherencia(documentos: list[Documento], ctx: Contexto) -> dict:
    hallazgos = []
    for doc in documentos:
        texto = doc.lectura.texto or ""
        ajenos = sorted({r for r in _RUC.findall(texto) if r != doc.ruc})
        if ajenos:
            hallazgos.append(_h(ALERTA, f"«{doc.nombre}» de {doc.postor} menciona otro RUC ({', '.join(ajenos)})",
                                "Un RUC distinto al del postor dentro de su propio documento suele ser un error de "
                                "«copia y pega» desde el documento de otra empresa.",
                                "Verifica quién elaboró realmente el documento.", doc.postor, doc.nombre))
        for m in _VIGENCIA.finditer(texto):
            vence = _fecha(*m.groups())
            if vence and vence < ctx.hoy:
                hallazgos.append(_h(ALERTA, f"«{doc.nombre}» de {doc.postor} venció el {vence:%d/%m/%Y}",
                                    "Un documento vencido no acredita lo que pretende.",
                                    "Pide la versión vigente.", doc.postor, doc.nombre))
        inicio = ctx.inicio_actividades.get(doc.postor_id)
        if doc.tipo == "certificado" and inicio:
            anteriores = [f for f in (_fecha(*g) for g in _FECHA.findall(texto)) if f and f < inicio]
            if anteriores:
                hallazgos.append(_h(ALERTA, f"«{doc.nombre}» acredita experiencia de {min(anteriores):%d/%m/%Y}, "
                                            f"antes de que {doc.postor} existiera",
                                    f"La empresa inició actividades el {inicio:%d/%m/%Y} según el padrón RUC.",
                                    "Ese certificado no puede ser de esta empresa: no lo tomes en cuenta.",
                                    doc.postor, doc.nombre))
        if doc.sha256 in ctx.reciclados:
            hallazgos.append(_h(ALERTA, f"«{doc.nombre}» es idéntico a un archivo de {', '.join(ctx.reciclados[doc.sha256])}",
                                "El mismo archivo exacto (misma huella SHA-256) ya se presentó en otro expediente.",
                                "Verifica si el documento se reutilizó indebidamente.", doc.postor, doc.nombre))
    duplicados: dict[str, list[Documento]] = {}
    for doc in documentos:
        duplicados.setdefault(doc.sha256, []).append(doc)
    for grupo in duplicados.values():
        if len({d.postor_id for d in grupo}) > 1:
            hallazgos.append(_h(ALERTA, "Dos postores presentaron exactamente el mismo archivo",
                                f"«{grupo[0].nombre}» aparece en: {', '.join(sorted({d.postor for d in grupo}))}.",
                                "Estos postores no son independientes.", None, grupo[0].nombre))
    return _bloque("coherencia", hallazgos,
                   "Sin RUC ajenos, documentos vencidos ni archivos reutilizados.",
                   huellas=[{"postor": d.postor, "documento": d.nombre, "sha256": d.sha256} for d in documentos])


# --- Conjunto --------------------------------------------------------------------------------

def analizar(documentos: list[Documento], ctx: Contexto) -> dict:
    bloques = {"montos": montos(documentos, ctx), "metadatos": metadatos(documentos, ctx),
               "similitud": similitud(documentos, ctx), "tdr": tdr(documentos, ctx),
               "coherencia": coherencia(documentos, ctx)}
    alertas = sum(1 for b in bloques.values() if b["estado"] == ALERTA)
    revisar = sum(1 for b in bloques.values() if b["estado"] == REVISAR)
    if alertas:
        veredicto = "anomalia"
        titulo = "Hay anomalías en la documentación"
    elif revisar:
        veredicto = "revisar"
        titulo = "Hay puntos por revisar en la documentación"
    else:
        veredicto = "conforme"
        titulo = "La documentación es coherente"
    hallazgos = [h for b in bloques.values() for h in b["hallazgos"]]
    postores_alerta = sorted({h["postor"] for h in hallazgos if h["nivel"] == ALERTA and h["postor"]
                              and "/" not in h["postor"]})
    if veredicto == "conforme":
        resumen = (f"Se revisaron {len(documentos)} documento(s). Los montos cuadran, los metadatos no muestran "
                   "vínculos entre postores, las propuestas cubren el TDR y no hay documentos vencidos ni reciclados.")
    else:
        con_problemas = [b["titulo"].lower() for b in bloques.values() if b["estado"] != LIMPIO]
        resumen = (f"Se revisaron {len(documentos)} documento(s); hay observaciones en "
                   f"{len(con_problemas)} de 5 bloques ({', '.join(con_problemas)}). "
                   + (f"Requieren especial atención: {', '.join(postores_alerta)}. " if postores_alerta else "")
                   + "Abre cada bloque para ver qué se encontró y qué hacer.")
    return {"veredicto": veredicto, "titulo": titulo, "resumen": resumen, "bloques": bloques,
            "benford": bloques["montos"]["detalle"]["benford"],
            "conteo": {"alerta": alertas, "revisar": revisar, "limpio": 5 - alertas - revisar}}
