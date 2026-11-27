"""Datos agregados del Dashboard, estrictamente filtrados por rol."""
from collections import Counter
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from conforme import bitacora, integridad, normativa, repositorio
from conforme.adaptadores import estado_adaptadores
from conforme.documentos import repositorio as doc_repo
from conforme.modelos import (
    ESTADO_CERRADA, ROL_ABASTECIMIENTO, ROL_AREA_USUARIA, ROL_AUDITOR, ROL_TESORERIA,
    Alerta, ConflictoInteres, Expediente, ExpedientePostor, RevisionDocumental, RevisionPrevia,
)
from conforme.permisos import Actor
from conforme.proveedores import dimensiones as dims_mod
from conforme.proveedores import repositorio as eval_repo

_BLOQUE_TITULO = {
    "montos": "Montos y Benford",
    "metadatos": "Metadatos PDF",
    "similitud": "Cruce entre postores",
    "tdr": "Cumplimiento TDR",
    "coherencia": "Vigencias y coherencia",
}


def _contar_alertas(alertas: list[dict]) -> dict:
    vigentes = [a for a in alertas if a.get("vigente") is not False]
    abiertas = [a for a in vigentes if a["estado"] != ESTADO_CERRADA]
    por_regla = Counter(a["regla"] for a in abiertas)
    return {
        "total": len(vigentes),
        "abiertas": len(abiertas),
        "altas": sum(1 for a in abiertas if a["severidad"] == "alta"),
        "medias": sum(1 for a in abiertas if a["severidad"] == "media"),
        "bloqueantes": sum(1 for a in abiertas if a.get("bloqueante")),
        "por_estado": dict(Counter(a["estado"] for a in vigentes)),
        "por_regla": [
            {"clave": r, "nombre": normativa.NOMBRE_REGLA.get(r, "Seguimiento de Auditoría" if r == "OCI" else r), "valor": n}
            for r, n in por_regla.most_common(7)
        ],
        "recientes": [
            {
                "id": a["id"], "expediente_id": a["expediente_id"], "expediente": a["expediente"],
                "regla": a["regla"],
                "nombre": normativa.NOMBRE_REGLA.get(a["regla"], "Seguimiento de Auditoría" if a["regla"] == "OCI" else a["regla"]),
                "severidad": a["severidad"], "estado": a["estado"], "ambito": a["ambito"],
                "explicacion": a["explicacion"], "puede_revisar": a.get("puede_revisar", False),
            }
            for a in abiertas[:6]
        ],
    }


def _resumen_preventivo(sesion: Session, actor: Actor) -> dict:
    evaluaciones = eval_repo.bandeja(sesion, actor)
    postores = list(sesion.scalars(select(ExpedientePostor)))
    veredictos = Counter()
    hallazgos_dim = Counter({k: 0 for k in dims_mod.DIMENSIONES})
    monto_riesgo = Decimal("0.00")

    for p in postores:
        if p.informe_consolidado:
            v = p.informe_consolidado.get("veredicto", "sin_consolidar")
            veredictos[v] += 1
            if v == "no_recomendado":
                monto_riesgo += Decimal(p.monto_cotizado)
        else:
            veredictos["sin_consolidar"] += 1
        for clave, res in (p.analisis_dimensiones or {}).items():
            if clave in hallazgos_dim and res.get("estado") in ("alerta", "revisar"):
                hallazgos_dim[clave] += 1

    # Revisión documental más reciente por expediente
    rev_docs = list(sesion.scalars(select(RevisionDocumental).order_by(RevisionDocumental.id.desc())))
    ultima_por_exp = {}
    for r in rev_docs:
        if r.expediente_id and r.expediente_id not in ultima_por_exp:
            ultima_por_exp[r.expediente_id] = r
    doc_veredictos = Counter(r.veredicto for r in ultima_por_exp.values())
    doc_bloques = Counter({k: 0 for k in _BLOQUE_TITULO})
    for r in ultima_por_exp.values():
        for k, b in (r.resultados_bloques or {}).items():
            if k in doc_bloques and b.get("estado") in ("alerta", "revisar"):
                doc_bloques[k] += 1

    embudo = [
        {"etapa": "TDR por revisar", "valor": sum(1 for e in evaluaciones if e["estado_flujo"] in ("requerimiento", "tdr_observado"))},
        {"etapa": "En evaluación (6 dim.)", "valor": sum(1 for e in evaluaciones if e["estado_flujo"] == "en_evaluacion_proveedores")},
        {"etapa": "Revisión independiente", "valor": sum(1 for e in evaluaciones if e["estado_flujo"] == "pendiente_revision_independiente")},
        {"etapa": "Selección aprobada", "valor": sum(1 for e in evaluaciones if e["estado_flujo"] == "seleccion_aprobada" or e["estado_revision_independiente"] == "aprobada")},
    ]

    prioritarios = sorted(
        evaluaciones,
        key=lambda e: (
            0 if e["me_toca_revisar"] else (1 if e["estado_flujo"] == "en_evaluacion_proveedores" else 2),
            -e["id"],
        ),
    )[:5]

    return {
        "evaluaciones_total": len(evaluaciones),
        "por_analizar": sum(1 for e in evaluaciones if e["estado_flujo"] == "en_evaluacion_proveedores"),
        "en_revision_independiente": sum(1 for e in evaluaciones if e["estado_flujo"] == "pendiente_revision_independiente"),
        "me_toca_revisar": sum(1 for e in evaluaciones if e["me_toca_revisar"]),
        "aprobadas": sum(1 for e in evaluaciones if e["estado_revision_independiente"] == "aprobada"),
        "postores_total": len(postores),
        "postores_no_recomendados": veredictos.get("no_recomendado", 0),
        "monto_riesgo_evitado": str(monto_riesgo),
        "veredictos_postores": [
            {"clave": "apto", "nombre": "Apto", "valor": veredictos.get("apto", 0), "tono": "verde"},
            {"clave": "apto_con_observaciones", "nombre": "Con observaciones", "valor": veredictos.get("apto_con_observaciones", 0), "tono": "ambar"},
            {"clave": "no_recomendado", "nombre": "No recomendado", "valor": veredictos.get("no_recomendado", 0), "tono": "rojo"},
            {"clave": "sin_consolidar", "nombre": "Pendiente", "valor": veredictos.get("sin_consolidar", 0), "tono": "neutro"},
        ],
        "hallazgos_por_dimension": [
            {"clave": k, "nombre": dims_mod.DIMENSIONES[k], "valor": hallazgos_dim[k]}
            for k in dims_mod.DIMENSIONES
        ],
        "embudo": embudo,
        "documentos": {
            "analizados": len(ultima_por_exp),
            "anomalias": doc_veredictos.get("anomalia", 0),
            "revisar": doc_veredictos.get("revisar", 0),
            "conformes": doc_veredictos.get("conforme", 0),
            "por_bloque": [
                {"clave": k, "nombre": _BLOQUE_TITULO[k], "valor": doc_bloques[k]}
                for k in _BLOQUE_TITULO
            ],
        },
        "casos_prioritarios": [
            {
                "id": e["id"], "codigo": e["codigo"], "descripcion": e["descripcion"],
                "area": e["area"], "monto": str(e["monto"]), "estado_flujo": e["estado_flujo"],
                "postores": e["postores"], "analizados": e["analizados"],
                "me_toca_revisar": e["me_toca_revisar"], "evaluador": e["evaluador"],
            }
            for e in prioritarios
        ],
    }


def _resumen_benford(sesion: Session, actor: Actor, fuente: str = "ordenes") -> dict:
    b = doc_repo.benford_transversal(sesion, actor, fuente=fuente)
    exceso = set(b.get("digitos_en_exceso") or [])
    return {
        "fuente": fuente,
        "nivel": b["nivel"],
        "titulo": b["titulo"],
        "resumen": b["lectura"],
        "total": b["total_montos"],
        "mad": b["mad"],
        "suficiente": b["muestra_suficiente"],
        "digitos": [
            {**d, "sospechoso": d["digito"] in exceso}
            for d in b["distribucion"]
        ],
    }


def resumen(sesion: Session, actor: Actor) -> dict:
    """Devuelve exclusivamente las métricas permitidas para el rol del actor."""
    base = repositorio.indicadores(sesion, actor)
    todas_alertas = repositorio.listar_alertas(sesion, actor)
    permisos = {
        "preventivo": actor.rol in (ROL_ABASTECIMIENTO, ROL_AUDITOR, ROL_TESORERIA),
        "benford": actor.rol in (ROL_ABASTECIMIENTO, ROL_AUDITOR, ROL_TESORERIA),
        "pagos": actor.rol in (ROL_TESORERIA, ROL_AUDITOR),
        "integridad": actor.rol == ROL_AUDITOR,
        "adaptadores": actor.rol in (ROL_ABASTECIMIENTO, ROL_AUDITOR, ROL_TESORERIA),
    }

    if actor.rol == ROL_ABASTECIMIENTO:
        # Resumen solo lectura de señales externas (proveedores/documentos) escaladas a Auditoría.
        # Nunca expone alertas internas (I1) a Abastecimiento.
        filas_ext = sesion.execute(
            select(
                Alerta.id, Alerta.expediente_id, Expediente.codigo.label("expediente"),
                Alerta.regla, Alerta.severidad, Alerta.estado, Alerta.ambito,
                Alerta.bloqueante, Alerta.explicacion,
            )
            .join(Expediente, Expediente.id == Alerta.expediente_id)
            .where(Alerta.regla.in_(("P1", "P2", "P3", "P4", "D1", "D2", "D3")))
            .order_by(Alerta.id.desc())
        )
        alertas_rol = [{**dict(f._mapping), "vigente": True, "puede_revisar": False} for f in filas_ext]
    elif actor.rol == ROL_TESORERIA:
        alertas_rol = [a for a in todas_alertas if a["ambito"] == "operativa_tesoreria"]
    elif actor.rol == ROL_AUDITOR:
        alertas_rol = [a for a in todas_alertas if a["ambito"] == "seguimiento_oci"] or todas_alertas
    else:
        alertas_rol = todas_alertas

    datos: dict = {
        "rol": actor.rol,
        "permisos": permisos,
        "resumen_general": {
            "expedientes": base["expedientes"],
            "por_semaforo": base["por_semaforo"],
            "con_conformidad": base["con_conformidad"],
            "sin_conformidad": base["sin_conformidad"],
            "por_pagar": base["por_pagar"],
            "con_observaciones_pendientes": base["con_observaciones_pendientes"],
        },
        "alertas": _contar_alertas(alertas_rol),
    }

    if permisos["preventivo"]:
        datos["preventivo"] = _resumen_preventivo(sesion, actor)

    if permisos["benford"]:
        fuente = "pagos" if actor.rol == ROL_TESORERIA else "ordenes"
        datos["benford"] = _resumen_benford(sesion, actor, fuente=fuente)

    if permisos["pagos"]:
        bandeja = repositorio.bandeja_pagos(sesion, actor)
        motivos = Counter(b["nombre"] for x in bandeja for b in x["bloqueos"])
        datos["pagos"] = {
            "listos": sum(1 for x in bandeja if x["estado_pago"] == "listo"),
            "bloqueados": sum(1 for x in bandeja if x["estado_pago"] == "bloqueado"),
            "pagados": sum(1 for x in bandeja if x["estado_pago"] == "pagado"),
            "por_motivo": [{"nombre": k, "valor": v} for k, v in motivos.most_common(6)],
        }

    if permisos["integridad"]:
        panel = integridad.panel(sesion, actor)
        cadena = bitacora.verificar_cadena_cacheada(sesion).resultado
        datos["integridad"] = {
            "conflictos_total": len(panel["conflictos"]),
            "conflictos_bloqueantes": panel["conflictos_bloqueantes"],
            "revisiones_pendientes": panel["revisiones_pendientes"],
            "seguimiento_abierto": panel["seguimiento_abierto"],
            "actuaciones": len(panel["actuaciones"]),
            "cadena_integra": cadena.integra,
            "registros_bitacora": cadena.total,
            "conflictos_recientes": panel["conflictos"][:5],
        }

    if permisos["adaptadores"]:
        datos["adaptadores"] = estado_adaptadores()

    return datos
