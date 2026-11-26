"""Motor de análisis precontractual por proveedor con simulación trazable de fuentes."""
from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256

from conforme.prevencion import demo
from conforme.prevencion.fuentes import CONOSCE, FUP, OECE, SUNAT

FUENTES_ANALISIS = [
    ("sunat", "F01", "Padrón tributario SUNAT", SUNAT),
    ("rnp", "F02", "Ficha Única y RNP (OECE)", FUP),
    ("tcp", "F03", "Inhabilitaciones y multas TCP", OECE),
    ("penalidad", "F05", "Historial de penalidades y trayectoria", OECE),
    ("vinculo", "F06", "Composición jurídica y vínculos", OECE),
    ("cotizacion", "F09", "Consistencia de cotización", CONOSCE),
]

FUENTES_COMPRA = [
    ("orden", "F08", "Órdenes previas similares (CONOSCE)", CONOSCE),
    ("competencia", "F09", "Cruce comparativo de cotizaciones", CONOSCE),
]


def _huella(clave: str, ruc: str | None) -> str:
    return sha256(f"sim:{clave}:{ruc or 'compra'}".encode()).hexdigest()[:18]


def _semilla(requerimiento: str, ruc: str) -> bytes:
    return sha256(f"{requerimiento}:{ruc}".encode()).digest()


def _perfil_candidatos(compra: dict) -> dict[str, str]:
    """Asigna perfiles deterministas y variados a los proveedores de una compra."""
    candidatos = compra["candidatos"]
    tiene_intervinientes = bool(compra.get("intervinientes"))
    rotacion = [
        "sancion_tcp",
        "limpio",
        "vinculo_interviniente" if tiene_intervinientes else "trayectoria_penalidad",
        "tributario_estado",
        "trayectoria_penalidad",
        "limpio",
    ]
    perfiles = {}
    if len(candidatos) == 1:
        unico = candidatos[0]
        semilla = _semilla(compra["requerimiento"], unico["ruc"])
        opciones = ("sancion_tcp", "trayectoria_penalidad", "tributario_estado")
        perfiles[unico["ruc"]] = opciones[semilla[0] % len(opciones)]
        return perfiles

    for indice, candidato in enumerate(candidatos):
        if indice < len(rotacion):
            perfiles[candidato["ruc"]] = rotacion[indice]
        else:
            semilla = _semilla(compra["requerimiento"], candidato["ruc"])
            perfiles[candidato["ruc"]] = rotacion[semilla[0] % len(rotacion)]
    return perfiles


def _nivel_proveedor(hallazgos: list[dict]) -> str:
    prioridades = {h["prioridad"] for h in hallazgos}
    if "verificar" in prioridades:
        return "verificar"
    if "aclarar" in prioridades:
        return "aclarar"
    if "contexto" in prioridades:
        return "contexto"
    return "limpio"


def _resumen_proveedor(hallazgos: list[dict]) -> str:
    if not hallazgos:
        return "Sin observaciones relevantes en las fuentes simuladas."
    verificar = sum(1 for h in hallazgos if h["prioridad"] == "verificar")
    aclarar = sum(1 for h in hallazgos if h["prioridad"] == "aclarar")
    contexto = sum(1 for h in hallazgos if h["prioridad"] == "contexto")
    partes = []
    if verificar:
        partes.append(f"{verificar} por verificar")
    if aclarar:
        partes.append(f"{aclarar} por aclarar")
    if contexto:
        partes.append(f"{contexto} de contexto")
    return " · ".join(partes).capitalize() + "."


def _pasos_demo(compra: dict, candidato: dict, hallazgos_demo: list[dict]) -> list[dict]:
    ruc = candidato["ruc"]
    corte = compra["fecha"]
    propios = [h for h in hallazgos_demo if h["ruc"] == ruc]
    por_frente = {h["frente"]: h for h in propios}

    pasos = []
    if "F04" in por_frente:
        h = por_frente["F04"]
        pasos.append(dict(
            fuente_id="sunat", fuente="Padrón tributario SUNAT", frente="F01",
            consulta="Validando estado tributario, condición y fecha de inicio de actividades…",
            estado="contexto",
            mensaje="ACTIVO · HABIDO · Inicio de actividades reciente (45 días).",
            hallazgo=h,
        ))
    else:
        pasos.append(dict(
            fuente_id="sunat", fuente="Padrón tributario SUNAT", frente="F01",
            consulta="Validando estado tributario, condición y razón social…",
            estado="ok",
            mensaje=f"ACTIVO · HABIDO · Razón social coincide con {candidato['nombre']}.",
            hallazgo=None,
        ))

    pasos.append(dict(
        fuente_id="rnp", fuente="Ficha Única y RNP (OECE)", frente="F02",
        consulta="Consultando inscripción vigente y capítulo de servicios…",
        estado="ok",
        mensaje=f"Inscripción vigente en capítulo correspondiente al rubro {compra['rubro']}.",
        hallazgo=None,
    ))

    if "F03" in por_frente:
        h = por_frente["F03"]
        pasos.append(dict(
            fuente_id="tcp", fuente="Inhabilitaciones y multas TCP", frente="F03",
            consulta="Cruzando RUC contra sanciones vigentes y resoluciones del TCP…",
            estado="alerta",
            mensaje="Coincidencia exacta en resolución TCP-DEMO-017 (requiere contraste con acto posterior).",
            hallazgo=h,
        ))
    else:
        pasos.append(dict(
            fuente_id="tcp", fuente="Inhabilitaciones y multas TCP", frente="F03",
            consulta="Cruzando RUC contra sanciones vigentes y resoluciones del TCP…",
            estado="ok",
            mensaje="Sin inhabilitaciones vigentes ni mandatos judiciales registrados.",
            hallazgo=None,
        ))

    pasos.append(dict(
        fuente_id="penalidad", fuente="Historial de penalidades y trayectoria", frente="F05",
        consulta="Revisando penalidades previas y órdenes comparables…",
        estado="ok",
        mensaje=f"Sin penalidades reportadas al corte {corte}.",
        hallazgo=None,
    ))

    if "F07" in por_frente:
        h = por_frente["F07"]
        pasos.append(dict(
            fuente_id="vinculo", fuente="Composición jurídica y vínculos", frente="F07",
            consulta="Contrastando representantes y socios con intervinientes de la compra…",
            estado="alerta",
            mensaje="Coincidencia declarada en DJI-DEMO-08 con el comprador designado.",
            hallazgo=h,
        ))
    else:
        pasos.append(dict(
            fuente_id="vinculo", fuente="Composición jurídica y vínculos", frente="F06",
            consulta="Contrastando representantes y socios con intervinientes de la compra…",
            estado="ok",
            mensaje="Sin coincidencias con intervinientes ni otros postores.",
            hallazgo=None,
        ))

    pasos.append(_paso_cotizacion(compra, candidato))
    return pasos


def _paso_cotizacion(compra: dict, candidato: dict) -> dict:
    importe_compra = Decimal(str(compra["importe"]))
    moneda = compra["moneda"]
    importe_cand = Decimal(str(candidato["importe"])) if candidato.get("importe") else None
    corte = compra["fecha"]

    if importe_cand is None:
        return dict(
            fuente_id="cotizacion", fuente="Consistencia de cotización", frente="F10",
            consulta="Verificando cotización frente al monto estimado de la compra…",
            estado="ok",
            mensaje="Sin importe de cotización registrado para contraste automático.",
            hallazgo=None,
        )

    variacion = ((importe_cand - importe_compra) / importe_compra) * Decimal("100")
    if variacion > Decimal("15"):
        hallazgo = dict(
            id=_huella("precio_alto", candidato["ruc"]),
            ruc=candidato["ruc"],
            frente="F10",
            prioridad="aclarar",
            titulo="Cotización por encima del valor estimado",
            detalle=(
                f"La oferta ({moneda} {importe_cand:,.2f}) supera en {variacion:.1f} % el importe estimado "
                f"({moneda} {importe_compra:,.2f}). Verifica alcance, impuestos y condiciones de entrega."
            ),
            evidencias=[dict(
                fuente="Análisis de cotización · simulación",
                fecha=corte,
                alcance="Simulación de contraste de precios",
                url=None,
                acto=candidato.get("proforma"),
                extracto=f"{candidato['nombre']} cotiza {moneda} {importe_cand:,.2f} frente a estimado de {moneda} {importe_compra:,.2f}.",
            )],
            simulado=True,
        )
        return dict(
            fuente_id="cotizacion", fuente="Consistencia de cotización", frente="F10",
            consulta="Verificando cotización frente al monto estimado de la compra…",
            estado="atencion",
            mensaje=f"Oferta {variacion:+.1f} % sobre el estimado ({moneda} {importe_cand:,.2f}).",
            hallazgo=hallazgo,
        )

    if variacion < Decimal("-30"):
        hallazgo = dict(
            id=_huella("precio_bajo", candidato["ruc"]),
            ruc=candidato["ruc"],
            frente="F10",
            prioridad="aclarar",
            titulo="Cotización inusualmente baja frente al estimado",
            detalle=(
                f"La oferta ({moneda} {importe_cand:,.2f}) está {abs(variacion):.1f} % por debajo del estimado "
                f"({moneda} {importe_compra:,.2f}). Confirma que cubra todos los entregables del TDR."
            ),
            evidencias=[dict(
                fuente="Análisis de cotización · simulación",
                fecha=corte,
                alcance="Simulación de contraste de precios",
                url=None,
                acto=candidato.get("proforma"),
                extracto=f"{candidato['nombre']} cotiza {moneda} {importe_cand:,.2f} ({variacion:.1f} % vs estimado).",
            )],
            simulado=True,
        )
        return dict(
            fuente_id="cotizacion", fuente="Consistencia de cotización", frente="F10",
            consulta="Verificando cotización frente al monto estimado de la compra…",
            estado="atencion",
            mensaje=f"Oferta {variacion:+.1f} % bajo el estimado ({moneda} {importe_cand:,.2f}).",
            hallazgo=hallazgo,
        )

    return dict(
        fuente_id="cotizacion", fuente="Consistencia de cotización", frente="F10",
        consulta="Verificando cotización frente al monto estimado de la compra…",
        estado="ok",
        mensaje=f"Oferta dentro de rango esperado ({moneda} {importe_cand:,.2f}, {variacion:+.1f} % vs estimado).",
        hallazgo=None,
    )


def _pasos_simulados(compra: dict, candidato: dict, perfil: str) -> list[dict]:
    ruc = candidato["ruc"]
    nombre = candidato["nombre"]
    corte = compra["fecha"]
    fecha_compra = date.fromisoformat(corte)
    semilla = _semilla(compra["requerimiento"], ruc)
    num_res = 210 + (int.from_bytes(semilla[:2], "big") % 680)
    num_orden = 104 + (int.from_bytes(semilla[2:4], "big") % 420)
    anio = fecha_compra.year
    acto_tcp = f"RES-SIM-{num_res:04d}-{anio}-TCE"
    acto_multa = f"MUL-SIM-{num_res:04d}-{anio}-TCE"
    acto_penalidad = f"PEN-SIM-{num_orden:03d}-{anio}"
    acto_dji = f"DJI-SIM-{num_orden:03d}-{anio}"

    pasos = []

    # 1. SUNAT
    if perfil == "tributario_estado":
        hallazgo_sunat = dict(
            id=_huella("sunat_estado", ruc),
            ruc=ruc,
            frente="F01",
            prioridad="aclarar",
            titulo="Condición tributaria por contrastar en SUNAT",
            detalle=(
                "El padrón simulado reporta condición 'NO HALLADO' y domicilio fiscal en actualización. "
                "Verifica la ficha RUC vigente antes de emitir la orden."
            ),
            evidencias=[dict(
                fuente="Padrón reducido SUNAT · simulación",
                fecha=corte,
                alcance="Simulación de padrón SUNAT",
                url=SUNAT,
                extracto=f"RUC {ruc} · {nombre} · Estado: ACTIVO · Condición: NO HALLADO.",
            )],
            simulado=True,
        )
        pasos.append(dict(
            fuente_id="sunat", fuente="Padrón tributario SUNAT", frente="F01",
            consulta="Validando estado tributario, condición y razón social…",
            estado="atencion",
            mensaje="ACTIVO · NO HALLADO · Domicilio fiscal requiere verificación oficial.",
            hallazgo=hallazgo_sunat,
        ))
    elif perfil == "trayectoria_penalidad":
        alta = fecha_compra - timedelta(days=52)
        hallazgo_alta = dict(
            id=_huella("trayectoria_alta", ruc),
            ruc=ruc,
            frente="F04",
            prioridad="contexto",
            titulo="Inicio de actividades reciente respecto al servicio",
            detalle=(
                f"La fecha de inicio de actividades simulada ({alta.isoformat()}) tiene menos de 90 días. "
                "Solicita sustento de capacidad operativa y experiencia para el rubro."
            ),
            evidencias=[dict(
                fuente="Padrón tributario SUNAT · simulación",
                fecha=alta.isoformat(),
                alcance="Simulación de padrón SUNAT",
                url=SUNAT,
                extracto=f"RUC {ruc} · {nombre} · Inicio de actividades: {alta.isoformat()} · Rubro: {compra['rubro']}.",
            )],
            simulado=True,
        )
        pasos.append(dict(
            fuente_id="sunat", fuente="Padrón tributario SUNAT", frente="F04",
            consulta="Validando estado tributario, condición y fecha de inicio de actividades…",
            estado="contexto",
            mensaje=f"ACTIVO · HABIDO · Inicio de actividades reciente ({alta.isoformat()}).",
            hallazgo=hallazgo_alta,
        ))
    else:
        pasos.append(dict(
            fuente_id="sunat", fuente="Padrón tributario SUNAT", frente="F01",
            consulta="Validando estado tributario, condición y razón social…",
            estado="ok",
            mensaje=f"ACTIVO · HABIDO · Razón social coincide con {nombre}.",
            hallazgo=None,
        ))

    # 2. RNP / FUP
    pasos.append(dict(
        fuente_id="rnp", fuente="Ficha Única y RNP (OECE)", frente="F02",
        consulta="Consultando inscripción vigente y capítulo aplicable en el RNP…",
        estado="ok",
        mensaje=f"Registro vigente en capítulo compatible con {compra['rubro']}.",
        hallazgo=None,
    ))

    # 3. TCP (Inhabilitaciones y multas)
    if perfil == "sancion_tcp":
        inicio = fecha_compra - timedelta(days=28)
        fin = fecha_compra + timedelta(days=152)
        hallazgo_tcp = dict(
            id=_huella("tcp_inhabilitacion", ruc),
            ruc=ruc,
            frente="F03",
            prioridad="verificar",
            titulo="Inhabilitación temporal publicada en TCP",
            detalle=(
                f"Se detectó una coincidencia exacta en el registro simulado del Tribunal de Contrataciones "
                f"({acto_tcp}, vigente del {inicio.isoformat()} al {fin.isoformat()}). "
                "Confirma en la FUP si existe recurso o suspensión posterior."
            ),
            evidencias=[dict(
                fuente="OECE · Inhabilitaciones TCP · simulación",
                fecha=corte,
                alcance="Simulación de sanciones vigentes TCP",
                url=OECE,
                acto=acto_tcp,
                extracto=f"{nombre} (RUC {ruc}) · {acto_tcp} · Vigencia: {inicio.isoformat()} a {fin.isoformat()} · Incumplimiento injustificado de contrato.",
            )],
            simulado=True,
        )
        pasos.append(dict(
            fuente_id="tcp", fuente="Inhabilitaciones y multas TCP", frente="F03",
            consulta="Cruzando RUC contra sanciones vigentes, multas y mandatos judiciales…",
            estado="alerta",
            mensaje=f"Coincidencia exacta en {acto_tcp} (inhabilitación temporal vigente).",
            hallazgo=hallazgo_tcp,
        ))
    elif perfil == "tributario_estado":
        hallazgo_multa = dict(
            id=_huella("tcp_multa", ruc),
            ruc=ruc,
            frente="F03",
            prioridad="aclarar",
            titulo="Multa publicada por el TCP pendiente de contraste",
            detalle=(
                f"El cruce simulado identifica la multa {acto_multa}. "
                "Contrasta su pago o suspensión vigente en la Ficha Única del Proveedor."
            ),
            evidencias=[dict(
                fuente="OECE · Multas TCP · simulación",
                fecha=corte,
                alcance="Simulación de multas TCP",
                url=OECE,
                acto=acto_multa,
                extracto=f"{nombre} (RUC {ruc}) · {acto_multa} · Multa de 5 UIT · Verificar constancia de pago.",
            )],
            simulado=True,
        )
        pasos.append(dict(
            fuente_id="tcp", fuente="Inhabilitaciones y multas TCP", frente="F03",
            consulta="Cruzando RUC contra sanciones vigentes, multas y mandatos judiciales…",
            estado="atencion",
            mensaje=f"Multa registrada ({acto_multa}); confirmar estado de pago o suspensión.",
            hallazgo=hallazgo_multa,
        ))
    else:
        pasos.append(dict(
            fuente_id="tcp", fuente="Inhabilitaciones y multas TCP", frente="F03",
            consulta="Cruzando RUC contra sanciones vigentes, multas y mandatos judiciales…",
            estado="ok",
            mensaje="Sin inhabilitaciones, multas ni mandatos judiciales vigentes.",
            hallazgo=None,
        ))

    # 4. Penalidades
    if perfil == "trayectoria_penalidad":
        fecha_pen = fecha_compra - timedelta(days=34)
        hallazgo_pen = dict(
            id=_huella("penalidad_mora", ruc),
            ruc=ruc,
            frente="F05",
            prioridad="aclarar",
            titulo="Penalidad previa por retraso en prestación similar",
            detalle=(
                f"Se registró una penalidad simulada el {fecha_pen.isoformat()} en un servicio de {compra['rubro'].lower()}. "
                "Evalúa el cumplimiento de plazos y solicita cronograma detallado."
            ),
            evidencias=[dict(
                fuente="OECE · Penalidades de contratistas · simulación",
                fecha=fecha_pen.isoformat(),
                alcance="Simulación de penalidades",
                url=OECE,
                acto=acto_penalidad,
                extracto=f"Contrato {acto_penalidad} · Penalidad por mora (8 % del monto) · Objeto: {compra['rubro']}.",
            )],
            simulado=True,
        )
        pasos.append(dict(
            fuente_id="penalidad", fuente="Historial de penalidades y trayectoria", frente="F05",
            consulta="Revisando penalidades previas y desempeño histórico en CONOSCE…",
            estado="atencion",
            mensaje=f"1 penalidad por mora reportada ({acto_penalidad}, {fecha_pen.isoformat()}).",
            hallazgo=hallazgo_pen,
        ))
    else:
        pasos.append(dict(
            fuente_id="penalidad", fuente="Historial de penalidades y trayectoria", frente="F05",
            consulta="Revisando penalidades previas y desempeño histórico en CONOSCE…",
            estado="ok",
            mensaje="Sin penalidades registradas en los últimos 24 meses.",
            hallazgo=None,
        ))

    # 5. Vínculos / Composición jurídica
    if perfil == "vinculo_interviniente" and compra.get("intervinientes"):
        interviniente = compra["intervinientes"][0]
        hallazgo_vinculo = dict(
            id=_huella("vinculo_dji", ruc),
            ruc=ruc,
            frente="F07",
            prioridad="verificar",
            titulo="Posible vínculo societario con interviniente de la compra",
            detalle=(
                f"El cruce simulado de composición jurídica y DJI detecta coincidencia con "
                f"{interviniente['designacion']} ({interviniente['rol']}). "
                "Deriva la comprobación del impedimento a revisión independiente."
            ),
            evidencias=[dict(
                fuente="Composición jurídica y DJI · simulación",
                fecha=corte,
                alcance="Simulación de cruce societario",
                url=OECE,
                acto=acto_dji,
                extracto=(
                    f"{nombre} (RUC {ruc}) · Referencia {acto_dji} · Coincidencia con interviniente "
                    f"{interviniente['designacion']} ({interviniente['rol']}, {interviniente['referencia']})."
                ),
            )],
            simulado=True,
        )
        pasos.append(dict(
            fuente_id="vinculo", fuente="Composición jurídica y vínculos", frente="F07",
            consulta="Contrastando representantes y socios con intervinientes de la compra…",
            estado="alerta",
            mensaje=f"Posible vínculo con {interviniente['designacion']} ({interviniente['rol']}) · {acto_dji}.",
            hallazgo=hallazgo_vinculo,
        ))
    else:
        pasos.append(dict(
            fuente_id="vinculo", fuente="Composición jurídica y vínculos", frente="F06",
            consulta="Contrastando representantes y socios con intervinientes de la compra…",
            estado="ok",
            mensaje="Sin vínculos declarados con intervinientes ni otros candidatos.",
            hallazgo=None,
        ))

    # 6. Cotización
    pasos.append(_paso_cotizacion(compra, candidato))
    return pasos


def _pasos_compra(compra: dict, *, es_demo: bool, hallazgos_demo: list[dict]) -> list[dict]:
    corte = compra["fecha"]
    pasos = []

    if es_demo:
        hallazgo_orden = next((h for h in hallazgos_demo if h["ruc"] is None), None)
        pasos.append(dict(
            fuente_id="orden", fuente="Órdenes previas similares (CONOSCE)", frente="F08",
            consulta="Buscando órdenes de la entidad con objeto similar en los últimos 90 días…",
            estado="atencion" if hallazgo_orden else "ok",
            mensaje="Se hallaron 2 órdenes previas con objeto similar (OS-DEMO-006)." if hallazgo_orden else "Sin órdenes repetidas.",
            hallazgo=hallazgo_orden,
        ))
    else:
        fecha_prev = date.fromisoformat(corte) - timedelta(days=38)
        hallazgo_orden = dict(
            id=_huella("ordenes_similares", None),
            ruc=None,
            frente="F08",
            prioridad="aclarar",
            titulo="Órdenes previas con objeto similar en los últimos 90 días",
            detalle=(
                f"El cruce simulado en CONOSCE ubica 2 órdenes emitidas por la entidad ({compra['entidad_ruc']}) "
                f"con alcance afín a «{compra['objeto'][:80]}». Verifica la unidad de necesidad y descarta fraccionamiento."
            ),
            evidencias=[dict(
                fuente="OECE · Órdenes de compra y servicio · simulación",
                fecha=fecha_prev.isoformat(),
                alcance="Simulación de órdenes 90 días",
                url=CONOSCE,
                acto=f"OS-SIM-{fecha_prev.year}-042",
                extracto=f"Entidad {compra['entidad_ruc']} · {fecha_prev.isoformat()} · Objeto afín en rubro {compra['rubro']}.",
            )],
            simulado=True,
        )
        pasos.append(dict(
            fuente_id="orden", fuente="Órdenes previas similares (CONOSCE)", frente="F08",
            consulta="Buscando órdenes de la entidad con objeto similar en los últimos 90 días…",
            estado="atencion",
            mensaje="2 órdenes comparables detectadas en los últimos 90 días (revisar unidad de necesidad).",
            hallazgo=hallazgo_orden,
        ))

    # Cruce de cotizaciones idénticas entre candidatos
    por_importe: dict[Decimal, list[dict]] = {}
    for c in compra["candidatos"]:
        if c.get("importe"):
            clave = Decimal(str(c["importe"]))
            por_importe.setdefault(clave, []).append(c)
    repetidas = [grupo for grupo in por_importe.values() if len(grupo) >= 2]
    if repetidas:
        evidencias = [
            dict(
                fuente="Cotización de la revisión",
                fecha=corte,
                alcance="Cruce comparativo de ofertas",
                url=None,
                acto=c.get("proforma"),
                extracto=f"{c['nombre']} (RUC {c['ruc']}) · {compra['moneda']} {Decimal(str(c['importe'])):,.2f}",
            )
            for grupo in repetidas for c in grupo
        ]
        hallazgo_comp = dict(
            id=_huella("cotizaciones_iguales", None),
            ruc=None,
            frente="F09",
            prioridad="aclarar",
            titulo="Coincidencia exacta en importes de cotización",
            detalle="Dos o más proveedores registran exactamente el mismo importe ofertado. Verifica independencia de cotizaciones y sustento de precios.",
            evidencias=evidencias,
            simulado=True,
        )
        pasos.append(dict(
            fuente_id="competencia", fuente="Cruce comparativo de cotizaciones", frente="F09",
            consulta="Contrastando importes y proformas entre proveedores registrados…",
            estado="atencion",
            mensaje="Dos o más cotizaciones presentan importes idénticos.",
            hallazgo=hallazgo_comp,
        ))
    else:
        pasos.append(dict(
            fuente_id="competencia", fuente="Cruce comparativo de cotizaciones", frente="F09",
            consulta="Contrastando importes y proformas entre proveedores registrados…",
            estado="ok",
            mensaje="No se detectaron importes idénticos ni anomalías entre las cotizaciones.",
            hallazgo=None,
        ))

    return pasos


def fuentes_simuladas(compra: dict, *, es_demo: bool) -> list[dict]:
    corte = compra["fecha"]
    alcance = "Datos del caso ficticio" if es_demo else "Simulación de fuentes oficiales"
    etiquetas = [
        ("sunat", "Padrón reducido SUNAT", SUNAT),
        ("rnp", "Ficha Única y RNP (OECE)", FUP),
        ("tcp", "OECE · Inhabilitaciones TCP", OECE),
        ("multa", "OECE · Multas TCP", OECE),
        ("penalidad", "OECE · Penalidades de contratistas", OECE),
        ("vinculo", "OECE · Composición jurídica declarada", OECE),
        ("orden", "OECE · Órdenes de compra y servicio", CONOSCE),
    ]
    return [
        dict(
            id=clave, nombre=nombre, estado="consultada", url=None if es_demo else url,
            fecha_corte=corte, alcance=alcance, cobertura="Modo simulación activo",
        )
        for clave, nombre, url in etiquetas
    ]


def plan_analisis(compra: dict, *, es_demo: bool, ruc: str | None = None) -> dict:
    """Construye el plan estructurado de pasos por proveedor y compra para transmisión en vivo."""
    hallazgos_demo = demo.resultados(compra)[1] if es_demo else []
    perfiles = {} if es_demo else _perfil_candidatos(compra)
    objetivos = [c for c in compra["candidatos"] if ruc is None or c["ruc"] == ruc]

    proveedores = []
    for candidato in objetivos:
        pasos = (
            _pasos_demo(compra, candidato, hallazgos_demo)
            if es_demo
            else _pasos_simulados(compra, candidato, perfiles[candidato["ruc"]])
        )
        hallazgos = [p["hallazgo"] for p in pasos if p["hallazgo"]]
        proveedores.append(dict(
            ruc=candidato["ruc"],
            nombre=candidato["nombre"],
            pasos=pasos,
            hallazgos=hallazgos,
            nivel=_nivel_proveedor(hallazgos),
            resumen=_resumen_proveedor(hallazgos),
        ))

    pasos_compra = _pasos_compra(compra, es_demo=es_demo, hallazgos_demo=hallazgos_demo) if ruc is None else []
    hallazgos_compra = [p["hallazgo"] for p in pasos_compra if p["hallazgo"]]

    return dict(
        proveedores=proveedores,
        pasos_compra=pasos_compra,
        hallazgos_compra=hallazgos_compra,
        fuentes=fuentes_simuladas(compra, es_demo=es_demo),
        total_pasos=sum(len(p["pasos"]) for p in proveedores) + len(pasos_compra),
    )


def documentos_simulados(ruc: str, acto: str | None, nombre: str | None = None) -> list[dict]:
    """Genera documentos ficticios trazables cuando se solicita investigación sobre un acto simulado."""
    etiqueta_nombre = nombre or f"Proveedor RUC {ruc}"
    codigo = acto or f"ACT-SIM-{ruc[-4:]}"
    return [
        dict(
            id=f"sim-{codigo[:20]}",
            titulo=f"Documento simulado {codigo}",
            fecha=None,
            url=None,
            paginas=[dict(
                numero=1,
                texto=(
                    f"El registro simulado {codigo} refiere observaciones asociadas a {etiqueta_nombre} "
                    f"(RUC {ruc}) que requieren contraste directo en el portal oficial antes de adjudicar."
                ),
            )],
        ),
        dict(
            id=f"sim-seg-{codigo[:16]}",
            titulo=f"Nota de verificación recomendada · {codigo}",
            fecha=None,
            url=None,
            paginas=[dict(
                numero=1,
                texto=(
                    f"Antes de emitir la orden a favor del RUC {ruc}, se recomienda verificar en la FUP "
                    f"la vigencia, descargos o recursos posteriores vinculados al acto {codigo}."
                ),
            )],
        ),
    ]
