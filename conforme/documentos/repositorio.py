"""Revisión documental y forense (Fase 3). Única puerta a sus datos.

Por rol (PLAN.md, sección 5):
- Abastecimiento: sube los documentos de los postores y corre el análisis.
- OCI: consulta todo y puede correr el análisis y la auditoría transversal de montos;
  nunca modifica documentos ni decisiones.
- Tesorería: consulta las señales documentales y de Benford antes del pago.
- Área usuaria: no accede.
"""
import hashlib
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Text, cast, func, select
from sqlalchemy.orm import Session

from conforme import bitacora
from conforme import repositorio as expedientes
from conforme.documentos import analisis, benford, lectura
from conforme.errores import ErrorValidacion
from conforme.modelos import (
    ROL_ABASTECIMIENTO, ROL_AUDITOR, ROL_TESORERIA, Area, DocumentoPostor, Entregable, Evidencia, Expediente,
    ExpedientePostor, Pago, Persona, Proveedor, RevisionDocumental,
)
from conforme.adaptadores import obtener_fuentes
from conforme.permisos import Actor, PermisoDenegado, exigir_rol

ROLES_LECTURA = (ROL_ABASTECIMIENTO, ROL_TESORERIA, ROL_AUDITOR)
ROLES_ANALISIS = (ROL_ABASTECIMIENTO,)
TAMANO_MAXIMO = 5 * 1024 * 1024
MAXIMO_POR_POSTOR = 6
MIMES_ADMITIDOS = {
    "application/pdf", "text/csv", "image/jpeg", "image/png",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _expediente(sesion: Session, actor: Actor, expediente_id: int) -> Expediente:
    exigir_rol(actor, *ROLES_LECTURA)
    return expedientes._expediente_en_alcance(sesion, actor, expediente_id)


def _nombre(sesion: Session, persona_id: int) -> str:
    persona = sesion.get(Persona, persona_id)
    return f"{persona.nombres} {persona.apellidos}" if persona else "—"


def _ultima_revision(sesion: Session, expediente_id: int) -> RevisionDocumental | None:
    return sesion.scalar(select(RevisionDocumental)
                         .where(RevisionDocumental.expediente_id == expediente_id,
                                RevisionDocumental.ambito == "expediente")
                         .order_by(RevisionDocumental.id.desc()).limit(1))


def bandeja(sesion: Session, actor: Actor) -> list[dict]:
    exigir_rol(actor, *ROLES_LECTURA)
    documentos = (select(func.count()).where(DocumentoPostor.expediente_id == Expediente.id)
                  .correlate(Expediente).scalar_subquery())
    postores = (select(func.count()).where(ExpedientePostor.expediente_id == Expediente.id)
                .correlate(Expediente).scalar_subquery())
    filas = sesion.execute(
        select(Expediente.id, Expediente.codigo, Expediente.descripcion, Expediente.estado_flujo,
               Expediente.fecha_requerimiento, Area.nombre.label("area"),
               postores.label("postores"), documentos.label("documentos"))
        .join(Area, Area.id == Expediente.area_id)
        .where(postores > 0)
        .order_by(Expediente.fecha_requerimiento.desc(), Expediente.id.desc()))
    resultado = []
    for f in filas:
        datos = dict(f._mapping)
        revision = _ultima_revision(sesion, f.id)
        datos["veredicto"] = revision.veredicto if revision else None
        datos["analizado_en"] = revision.creado_en if revision else None
        resultado.append(datos)
    return resultado


def obtener(sesion: Session, actor: Actor, expediente_id: int) -> dict:
    _expediente(sesion, actor, expediente_id)
    expediente = expedientes.obtener_expediente(sesion, actor, expediente_id)
    postores = []
    for p in sesion.scalars(select(ExpedientePostor).where(ExpedientePostor.expediente_id == expediente_id)
                            .order_by(ExpedientePostor.id)):
        docs = [dict(f._mapping) for f in sesion.execute(
            select(DocumentoPostor.id, DocumentoPostor.tipo, DocumentoPostor.nombre_archivo,
                   DocumentoPostor.mime, DocumentoPostor.tamano, DocumentoPostor.sha256, DocumentoPostor.subido_en)
            .where(DocumentoPostor.postor_id == p.id).order_by(DocumentoPostor.id))]
        postores.append({"id": p.id, "ruc": p.ruc, "razon_social": p.razon_social, "estado": p.estado,
                         "documentos": docs})
    revision = _ultima_revision(sesion, expediente_id)
    puede_subir = actor.rol == ROL_ABASTECIMIENTO and expediente["estado_flujo"] != "pagado"
    return {
        "expediente": expediente, "postores": postores, "tipos": analisis.TIPOS, "bloques": analisis.BLOQUES,
        "revision": None if revision is None else {
            "id": revision.id, "veredicto": revision.veredicto, "resumen": revision.resumen_agente,
            "resultados": revision.resultados_bloques, "benford": revision.benford, "archivos": revision.archivos,
            "creado_en": revision.creado_en, "creado_por": _nombre(sesion, revision.creado_por),
        },
        "puede_subir": puede_subir,
        "puede_analizar": actor.rol in ROLES_ANALISIS,
        "documentos_cambiaron": bool(revision) and _huella_documentos(sesion, expediente_id) != (revision.archivos or {}).get("huella"),
    }


def _huella_documentos(sesion: Session, expediente_id: int) -> str:
    huellas = sorted(sesion.scalars(select(DocumentoPostor.sha256 + ":" + cast(DocumentoPostor.postor_id, Text))
                                    .where(DocumentoPostor.expediente_id == expediente_id)))
    return hashlib.sha256("|".join(huellas).encode()).hexdigest()


def subir_documento(sesion: Session, actor: Actor, expediente_id: int, postor_id: int, *, tipo: str,
                    nombre_archivo: str, mime: str | None, contenido: bytes) -> int:
    exigir_rol(actor, ROL_ABASTECIMIENTO)
    expediente = expedientes._expediente_en_alcance(sesion, actor, expediente_id, bloquear=True)
    if expediente.estado_flujo == "pagado":
        raise ErrorValidacion("El expediente ya está pagado: no se agregan documentos de postores.")
    postor = sesion.get(ExpedientePostor, postor_id)
    if postor is None or postor.expediente_id != expediente_id:
        raise ErrorValidacion("El postor no pertenece a este expediente.")
    if tipo not in analisis.TIPOS:
        raise ErrorValidacion("Elige el tipo de documento.")
    nombre = (nombre_archivo or "documento").strip()[:200]
    if not contenido:
        raise ErrorValidacion("El archivo está vacío.")
    if len(contenido) > TAMANO_MAXIMO:
        raise ErrorValidacion("El archivo supera los 5 MB.")
    formato = lectura.formato_de(nombre, mime)
    mime_final = mime if mime in MIMES_ADMITIDOS else {
        "pdf": "application/pdf", "csv": "text/csv",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}.get(formato)
    if mime_final is None:
        raise ErrorValidacion("Formato no admitido. Sube PDF, Word (.docx), Excel (.xlsx), CSV o imagen JPG/PNG.")
    cantidad = sesion.scalar(select(func.count()).where(DocumentoPostor.postor_id == postor_id))
    if cantidad >= MAXIMO_POR_POSTOR:
        raise ErrorValidacion(f"Cada postor admite hasta {MAXIMO_POR_POSTOR} documentos.")
    sha = hashlib.sha256(contenido).hexdigest()
    if sesion.scalar(select(DocumentoPostor.id).where(DocumentoPostor.postor_id == postor_id,
                                                      DocumentoPostor.sha256 == sha)):
        raise ErrorValidacion("Ese mismo archivo ya está cargado para este postor.")
    documento = DocumentoPostor(expediente_id=expediente_id, postor_id=postor_id, tipo=tipo,
                                nombre_archivo=nombre, mime=mime_final, tamano=len(contenido), sha256=sha,
                                contenido=contenido, subido_por=actor.persona_id,
                                subido_en=datetime.now(timezone.utc))
    sesion.add(documento)
    sesion.flush()
    bitacora.registrar(sesion, actor_id=actor.persona_id, accion="documento.presentado", entidad="documento_postor",
                       entidad_id=documento.id, expediente_id=expediente_id, documento_sha256=sha,
                       detalle={"documento": nombre, "tipo": tipo, "postor": postor.razon_social,
                                "resumen": f"{analisis.TIPOS[tipo]} de {postor.razon_social}: {nombre}."})
    return documento.id


def quitar_documento(sesion: Session, actor: Actor, expediente_id: int, documento_id: int) -> None:
    exigir_rol(actor, ROL_ABASTECIMIENTO)
    expediente = expedientes._expediente_en_alcance(sesion, actor, expediente_id, bloquear=True)
    if expediente.estado_flujo == "pagado":
        raise ErrorValidacion("El expediente ya está pagado: sus documentos no se modifican.")
    documento = sesion.get(DocumentoPostor, documento_id)
    if documento is None or documento.expediente_id != expediente_id:
        raise ErrorValidacion("El documento no pertenece a este expediente.")
    bitacora.registrar(sesion, actor_id=actor.persona_id, accion="documento.retirado", entidad="documento_postor",
                       entidad_id=documento.id, expediente_id=expediente_id, documento_sha256=documento.sha256,
                       detalle={"documento": documento.nombre_archivo,
                                "resumen": f"Documento retirado: {documento.nombre_archivo}."})
    sesion.delete(documento)
    sesion.flush()


def descargar(sesion: Session, actor: Actor, documento_id: int) -> dict:
    exigir_rol(actor, *ROLES_LECTURA)
    documento = sesion.get(DocumentoPostor, documento_id)
    if documento is None:
        raise PermisoDenegado("Documento inexistente o fuera de tu alcance.")
    expedientes._expediente_en_alcance(sesion, actor, documento.expediente_id)
    return {"nombre": documento.nombre_archivo, "mime": documento.mime, "contenido": bytes(documento.contenido)}


def analizar(sesion: Session, actor: Actor, expediente_id: int) -> dict:
    exigir_rol(actor, *ROLES_ANALISIS)
    expediente = expedientes._expediente_en_alcance(sesion, actor, expediente_id)
    postores = {p.id: p for p in sesion.scalars(select(ExpedientePostor)
                                                .where(ExpedientePostor.expediente_id == expediente_id))}
    filas = list(sesion.scalars(select(DocumentoPostor).where(DocumentoPostor.expediente_id == expediente_id)
                                .order_by(DocumentoPostor.id)))
    if not filas:
        raise ErrorValidacion("No hay documentos de los postores que analizar. Súbelos primero.")
    documentos = [analisis.Documento(
        id=d.id, postor_id=d.postor_id, postor=postores[d.postor_id].razon_social, ruc=postores[d.postor_id].ruc,
        tipo=d.tipo, nombre=d.nombre_archivo, sha256=d.sha256,
        lectura=lectura.leer(d.nombre_archivo, d.mime, bytes(d.contenido))) for d in filas]
    huellas = {d.sha256 for d in filas}
    reciclados: dict[str, list[str]] = {}
    for sha, codigo in sesion.execute(
            select(DocumentoPostor.sha256, Expediente.codigo).join(Expediente, Expediente.id == DocumentoPostor.expediente_id)
            .where(DocumentoPostor.sha256.in_(huellas), DocumentoPostor.expediente_id != expediente_id)):
        reciclados.setdefault(sha, []).append(codigo)
    for sha in sesion.scalars(select(Evidencia.sha256).where(Evidencia.sha256.in_(huellas))):
        reciclados.setdefault(sha, []).append("una evidencia de conformidad")
    inicio = {}
    adaptador_fuentes = obtener_fuentes()
    for p in postores.values():
        ficha = adaptador_fuentes.consultar_empresa(p.ruc, p.razon_social)
        if not ficha.padron.generico:
            inicio[p.id] = ficha.padron.inicio_actividades
    entregables = list(sesion.scalars(select(Entregable.descripcion).where(Entregable.expediente_id == expediente_id)
                                      .order_by(Entregable.numero)))
    ctx = analisis.Contexto(hoy=date.today(), entregables=entregables, inicio_actividades=inicio,
                            descripcion=expediente.descripcion,
                            reciclados={k: sorted(set(v)) for k, v in reciclados.items()})
    resultado = analisis.analizar(documentos, ctx)
    archivos = {
        "huella": _huella_documentos(sesion, expediente_id),
        "documentos": [{"id": d.id, "postor": d.postor, "nombre": d.nombre, "tipo": d.tipo, "sha256": d.sha256,
                        "formato": d.lectura.formato, "aviso": d.lectura.aviso} for d in documentos],
    }
    revision = RevisionDocumental(
        ambito="expediente", expediente_id=expediente_id, archivos=archivos,
        resultados_bloques=resultado["bloques"], benford=resultado["benford"], veredicto=resultado["veredicto"],
        resumen_agente=resultado["resumen"], creado_por=actor.persona_id, creado_en=datetime.now(timezone.utc))
    sesion.add(revision)
    sesion.flush()
    from conforme.proveedores import alertas as alertas_prev
    mapa_doc = {"metadatos": "D1", "similitud": "D1", "montos": "D2", "coherencia": "D3"}
    propuestas_doc = []
    for clave_b, regla in mapa_doc.items():
        bloque = resultado["bloques"].get(clave_b)
        if bloque and bloque["estado"] in ("alerta", "revisar"):
            alta = bloque["estado"] == "alerta"
            propuestas_doc.append({
                "regla": regla,
                "clave": f"doc-{clave_b}",
                "severidad": "alta" if alta else "media",
                "bloqueante": False,
                "ambito": "seguimiento_oci",
                "explicacion": f"Revisión documental ({bloque['titulo']}): {bloque['resumen']}",
                "datos": {"bloque": clave_b, "revision_id": revision.id},
            })
    alertas_prev.sincronizar_alertas(sesion, expediente_id, propuestas_doc)
    conteo = resultado["conteo"]
    bitacora.registrar(sesion, actor_id=actor.persona_id, accion="documentos.analizados",
                       entidad="revision_documental", entidad_id=revision.id, expediente_id=expediente.id,
                       detalle={"veredicto": resultado["veredicto"], "documentos": len(documentos),
                                "resumen": f"Revisión documental de {len(documentos)} documento(s): "
                                           f"{resultado['titulo'].lower()} ({conteo['alerta']} bloque(s) en alerta, "
                                           f"{conteo['revisar']} por revisar)."})
    return {"veredicto": resultado["veredicto"], "titulo": resultado["titulo"], "conteo": conteo}


# --- Auditoría transversal de montos (Benford) -------------------------------------------

def benford_transversal(sesion: Session, actor: Actor, *, fuente: str = "ordenes", area_id: int | None = None,
                        ruc: str | None = None, desde: date | None = None, hasta: date | None = None) -> dict:
    exigir_rol(actor, *ROLES_LECTURA)
    if fuente not in ("ordenes", "pagos"):
        raise ErrorValidacion("Elige órdenes o pagos.")
    if fuente == "ordenes":
        consulta = (select(Expediente.codigo, Expediente.monto, Expediente.fecha_orden.label("fecha"))
                    .where(Expediente.fecha_orden.isnot(None)))
    else:
        consulta = (select(Expediente.codigo, Pago.monto, Pago.fecha_pago.label("fecha"))
                    .join(Expediente, Expediente.id == Pago.expediente_id))
    columna_fecha = Expediente.fecha_orden if fuente == "ordenes" else Pago.fecha_pago
    if area_id:
        consulta = consulta.where(Expediente.area_id == area_id)
    if ruc:
        consulta = consulta.join(Proveedor, Proveedor.id == Expediente.proveedor_id).where(Proveedor.ruc == ruc.strip())
    if desde:
        consulta = consulta.where(columna_fecha >= desde)
    if hasta:
        consulta = consulta.where(columna_fecha <= hasta)
    filas = list(sesion.execute(consulta))
    resultado = benford.analizar([(f.codigo, Decimal(f.monto)) for f in filas])
    resultado["fuente"] = fuente
    resultado["monto_total"] = str(sum((Decimal(f.monto) for f in filas), Decimal("0")))
    resultado["areas"] = [{"id": i, "nombre": n} for i, n in sesion.execute(select(Area.id, Area.nombre).order_by(Area.nombre))]
    return resultado
