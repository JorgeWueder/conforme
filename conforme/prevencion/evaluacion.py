"""Cruces reproducibles con ediciones publicadas antes de la compra."""
from collections import defaultdict
from datetime import date, timedelta
from hashlib import sha256
from unicodedata import normalize
import re
from decimal import Decimal

from sqlalchemy import select, func

from conforme.modelos import PrevencionEdicion as Edicion, PrevencionRegistro as Registro
from conforme.prevencion.fuentes import FUENTES

ATENCION = {
    "tcp": ("verificar", "Inhabilitación publicada por verificar", "Confirma en la FUP el acto y su vigencia a la fecha de la compra."),
    "judicial": ("verificar", "Mandato judicial publicado", "Contrasta con el acto original, sus fechas y cualquier cambio posterior."),
    "multa": ("aclarar", "Multa publicada", "Confirma su estado y alcance en la fuente oficial."),
    "penalidad": ("contexto", "Penalidades en contratos previos", "Contrasta el motivo, el tipo de servicio y los contratos cubiertos."),
}
_TOKENS_IGNORADOS = {"para", "servicio", "servicios", "compra", "contratacion", "adquisicion", "suministro"}


def texto_normalizado(texto: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()))


def _tokens(texto):
    return set(texto_normalizado(texto).split()) - _TOKENS_IGNORADOS


def _evidencia(edicion, registro, campos=None):
    datos = registro.datos
    if campos is None:
        campos = ("nombre", "estado", "condicion", "acto", "inicio", "fin", "fecha", "motivo", "objeto", "importe", "moneda")
    return dict(
        fuente=FUENTES[edicion.fuente].nombre,
        fecha=edicion.fecha_corte.isoformat(),
        alcance=edicion.alcance,
        url=edicion.manifiesto.get("origen") or FUENTES[edicion.fuente].url,
        fila=registro.fila, sha256=edicion.sha256,
        acto=datos.get("acto"), url_acto=datos.get("url_acto"),
        extracto=" · ".join(str(datos[campo]) for campo in campos if datos.get(campo)),
    )


def _hallazgo(clave, ruc, prioridad, titulo, detalle, evidencias, *, frente=None):
    huella = sha256(f"{clave}:{ruc}".encode()).hexdigest()[:18]
    return dict(id=huella, ruc=ruc, frente=frente or FUENTES[clave].frente, prioridad=prioridad,
                titulo=titulo, detalle=detalle, evidencias=evidencias)


def _ediciones(sesion, fecha):
    prioridad = func.row_number().over(
        partition_by=(Edicion.fuente, Edicion.alcance),
        order_by=(Edicion.fecha_corte.desc(), Edicion.id.desc()),
    ).label("posicion")
    versiones = select(Edicion.id, prioridad).where(Edicion.fecha_corte <= fecha).subquery()
    consulta = (select(Edicion).join(versiones, versiones.c.id == Edicion.id).where(versiones.c.posicion == 1)
                .order_by(Edicion.fuente, Edicion.alcance))
    return list(sesion.scalars(consulta))



def _ordenes(sesion, ediciones, compra, fecha):
    if not ediciones:
        return [], {}, False
    inicio = (fecha - timedelta(days=90)).isoformat()
    fecha_orden = Registro.datos["fecha"].astext
    entidad = Registro.datos["entidad_ruc"].astext
    consulta = select(Registro).where(
        Registro.edicion_id.in_(ediciones), entidad == compra["entidad_ruc"],
        fecha_orden >= inicio, fecha_orden < fecha.isoformat(),
    ).order_by(fecha_orden.desc(), Registro.edicion_id.desc(), Registro.fila).limit(2001)
    registros = sesion.scalars(consulta).all()
    objetivo = _tokens(compra["objeto"])
    comparables = []
    por_ruc = defaultdict(int)
    vistos = set()
    for fila in registros[:2000]:
        datos = fila.datos
        estado = texto_normalizado(datos.get("estado", ""))
        if any(palabra in estado for palabra in ("anul", "cancel", "inval")):
            continue
        palabras = _tokens(datos.get("objeto", ""))
        if len(objetivo & palabras) < 2 or len(objetivo & palabras) * 2 < len(objetivo | palabras):
            continue
        identificador = (datos.get("acto"), datos.get("fecha"), fila.ruc)
        if identificador in vistos:
            continue
        vistos.add(identificador)
        por_ruc[fila.ruc] += 1
        comparables.append(fila)
    return comparables, por_ruc, len(registros) > 2000


def _primeras_ordenes(sesion, ediciones, candidatos, fecha):
    if not ediciones:
        return []
    fecha_orden = Registro.datos["fecha"].astext
    numero = func.row_number().over(
        partition_by=Registro.ruc, order_by=(fecha_orden, Registro.edicion_id, Registro.fila),
    ).label("posicion")
    candidatos_publicos = (
        select(Registro.edicion_id, Registro.fila, numero)
        .where(Registro.edicion_id.in_(ediciones), Registro.ruc.in_(candidatos),
               fecha_orden < fecha.isoformat())
        .subquery()
    )
    return sesion.scalars(
        select(Registro).join(candidatos_publicos, (Registro.edicion_id == candidatos_publicos.c.edicion_id)
                              & (Registro.fila == candidatos_publicos.c.fila))
        .where(candidatos_publicos.c.posicion == 1)
    ).all()


def _cotizaciones(compra):
    por_importe = defaultdict(list)
    for candidato in compra["candidatos"]:
        if candidato["importe"] and candidato["proforma"]:
            por_importe[Decimal(candidato["importe"])].append(candidato)
    coincidencias = [grupo for grupo in por_importe.values() if len(grupo) >= 2]
    if not coincidencias:
        return []
    evidencias = [
        dict(fuente="Cotización de la revisión", fecha=compra["fecha"], acto=c["proforma"],
             extracto=f"{c['nombre']} · {compra['moneda']} {c['importe']}")
        for grupo in coincidencias for c in grupo
    ]
    return [_hallazgo("cotizaciones", None, "contexto", "Coincidencia en importes de cotización",
                      "Contrasta si las ofertas corresponden al mismo alcance y si los precios son habituales.",
                      evidencias, frente="F09")]


def cruzar(sesion, compra: dict) -> tuple[list[dict], list[dict]]:
    fecha = date.fromisoformat(compra["fecha"])
    candidatos = {c["ruc"]: c for c in compra["candidatos"]}
    ediciones = _ediciones(sesion, fecha)
    por_id = {e.id: e for e in ediciones}
    por_fuente = defaultdict(list)
    for edicion in ediciones:
        por_fuente[edicion.fuente].append(edicion)

    fuentes = []
    hallazgos = _cotizaciones(compra)
    for clave, fuente in FUENTES.items():
        grupo = por_fuente.get(clave, [])
        if not grupo:
            fuentes.append(dict(id=clave, nombre=fuente.nombre, estado="sin_edicion", url=fuente.url))
            continue
        for edicion in grupo:
            vieja = fuente.max_dias is not None and (fecha - edicion.fecha_corte).days > fuente.max_dias
            fuentes.append(dict(
                id=f"{clave}:{edicion.id}", nombre=fuente.nombre,
                estado="desactualizada" if vieja else "consultada", url=fuente.url,
                fecha_corte=edicion.fecha_corte.isoformat(), alcance=edicion.alcance,
                cobertura=edicion.manifiesto.get("cobertura"),
            ))

    # Un máximo por fuente y candidato conserva la cobertura incluso con proveedores de alto volumen.
    numero = func.row_number().over(
        partition_by=(Edicion.fuente, Registro.ruc),
        order_by=(Edicion.fecha_corte.desc(), Registro.edicion_id.desc(), Registro.fila),
    ).label("posicion")
    rango = (select(Registro.edicion_id, Registro.fila, numero)
             .join(Edicion, Edicion.id == Registro.edicion_id)
             .where(Registro.edicion_id.in_(por_id), Registro.ruc.in_(candidatos))
             .subquery())
    filas = sesion.scalars(
        select(Registro).join(rango, (Registro.edicion_id == rango.c.edicion_id) & (Registro.fila == rango.c.fila))
        .where(rango.c.posicion <= 11)
        .order_by(rango.c.posicion)
    ).all()
    coincidencias = defaultdict(list)
    for fila in filas:
        clave = por_id[fila.edicion_id].fuente
        if clave != "penalidad" or (fila.datos.get("fecha") or "") < fecha.isoformat():
            coincidencias[clave, fila.ruc].append(fila)

    for (clave, ruc), registros in coincidencias.items():
        trazas = [_evidencia(por_id[f.edicion_id], f) for f in registros[:10]]
        if clave in ATENCION:
            prioridad, titulo, detalle = ATENCION[clave]
            if len(registros) > 10:
                detalle += " Se muestran las primeras diez coincidencias."
            hallazgos.append(_hallazgo(clave, ruc, prioridad, titulo, detalle, trazas))
        if clave == "sunat":
            datos = registros[0].datos
            estado = texto_normalizado(datos.get("estado", ""))
            condicion = texto_normalizado(datos.get("condicion", ""))
            nombre = texto_normalizado(datos.get("nombre", ""))
            cambio = nombre != texto_normalizado(candidatos[ruc]["nombre"])
            if cambio or estado != "activo" or condicion != "habido":
                hallazgos.append(_hallazgo(
                    clave, ruc, "aclarar", "Datos tributarios por contrastar",
                    "Coteja la razón social, el estado y la condición con la consulta oficial.", trazas,
                ))
        if clave == "vinculo":
            # La comprobación de relaciones personales se ejecuta en el canal autorizado.
            hallazgos.append(_hallazgo(
                clave, ruc, "contexto", "Composición jurídica registrada",
                "Verifica la representación y cualquier coincidencia relevante con la documentación registral.",
                [dict(fuente=FUENTES[clave].nombre, fecha=trazas[0]["fecha"], url=FUENTES[clave].url,
                      extracto="La edición contiene una referencia al RUC del candidato.")],
            ))

    ediciones_orden = [e.id for e in por_fuente.get("orden", [])]
    for fila in _primeras_ordenes(sesion, ediciones_orden, candidatos, fecha):
        hallazgos.append(_hallazgo(
            "trayectoria", fila.ruc, "contexto", "Primera orden observada en el historial",
            f"La primera orden visible se emitió el {fila.datos['fecha']}. "
            "Contrasta la capacidad para este servicio y las fechas de constitución o inicio de actividades.",
            [_evidencia(por_id[fila.edicion_id], fila)], frente="F04",
        ))
    ordenes, recuento, parcial = _ordenes(sesion, ediciones_orden, compra, fecha)
    if len(ordenes) >= 2:
        limite = " Se examinaron hasta 2 000 órdenes de la entidad." if parcial else ""
        hallazgos.append(_hallazgo(
            "orden", None, "aclarar", "Órdenes previas con objeto similar",
            f"Se encontraron {len(ordenes)} órdenes con objeto similar en los 90 días previos. "
            "Contrasta la unidad de necesidad y el sustento de cada compra." + limite,
            [_evidencia(por_id[f.edicion_id], f) for f in ordenes[:8]],
        ))
        for ruc, cantidad in recuento.items():
            if ruc in candidatos and cantidad >= 2:
                detalle = (f"El proveedor figura en {cantidad} de {len(ordenes)} órdenes comparables "
                           "de la entidad dentro de la cobertura consultada." + limite)
                hallazgos.append(_hallazgo(
                    "orden", ruc, "contexto", "Participación en órdenes comparables", detalle,
                    [_evidencia(por_id[f.edicion_id], f) for f in ordenes if f.ruc == ruc][:8],
                ))
    return fuentes, hallazgos
