"""Motor de reglas: arma la foto de cada expediente, evalúa R1–R8 y sincroniza
la tabla `alerta`. Sin aprendizaje automático: cada alerta explica sus cifras.

Es idempotente: la clave única (expediente, regla, clave) impide duplicados.
Una alerta ya creada no se borra aunque su condición desaparezca; la cierra
una persona con un motivo.
"""
from collections import defaultdict
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session

from conforme import bitacora, normativa
from conforme.modelos import (
    ESTADO_ABIERTA, ESTADO_CERRADA, Alerta, Conformidad, ConformidadEntregable,
    Entregable, Evidencia, Expediente, Pago, Persona, Proveedor,
)
from conforme.reglas import (
    r1_sin_evidencia, r2_penalidad, r3_conformidad_tardia, r4_misma_persona,
    r5_pago_sin_conformidad, r6_recurrencia_proveedor, r7_compras_sucesivas,
    r8_fechas_incoherentes,
)
from conforme.reglas.modelo import (
    AlertaPropuesta, ConformidadFoto, EntregableFoto, FotoExpediente, PagoFoto, VecinoFoto,
)

REGLAS = (
    r1_sin_evidencia.evaluar,
    r2_penalidad.evaluar,
    r3_conformidad_tardia.evaluar,
    r4_misma_persona.evaluar,
    r5_pago_sin_conformidad.evaluar,
    r6_recurrencia_proveedor.evaluar,
    r7_compras_sucesivas.evaluar,
    r8_fechas_incoherentes.evaluar,
)


def evaluar(foto: FotoExpediente) -> list[AlertaPropuesta]:
    return [propuesta for regla in REGLAS for propuesta in regla(foto)]


def cargar_fotos(sesion: Session, expediente_ids: list[int] | None = None) -> list[FotoExpediente]:
    """Fotos de los expedientes indicados (o de todos), con pocas consultas."""
    def acotar(consulta, columna):
        return consulta if expediente_ids is None else consulta.where(columna.in_(expediente_ids))

    conformidades = {
        f.expediente_id: ConformidadFoto(
            f.conformante_id, f.conformante, f.fecha_conformidad, f.penalidad_aplicada)
        for f in sesion.execute(acotar(
            select(
                Conformidad.expediente_id, Conformidad.conformante_id,
                func.concat(Persona.nombres, " ", Persona.apellidos).label("conformante"),
                Conformidad.fecha_conformidad, Conformidad.penalidad_aplicada,
            ).join(Persona, Persona.id == Conformidad.conformante_id),
            Conformidad.expediente_id,
        ))
    }

    entregables = defaultdict(list)
    for f in sesion.execute(acotar(
        select(
            Entregable.expediente_id, Entregable.numero, Entregable.descripcion,
            ConformidadEntregable.cumplido, func.count(Evidencia.id).label("n_evidencias"),
        )
        .outerjoin(ConformidadEntregable, ConformidadEntregable.entregable_id == Entregable.id)
        .outerjoin(Evidencia, Evidencia.conformidad_entregable_id == ConformidadEntregable.id)
        .group_by(Entregable.id, ConformidadEntregable.id)
        .order_by(Entregable.expediente_id, Entregable.numero),
        Entregable.expediente_id,
    )):
        entregables[f.expediente_id].append(
            EntregableFoto(f.numero, f.descripcion, f.cumplido, f.n_evidencias))

    pagos = defaultdict(list)
    for f in sesion.execute(acotar(
        select(Pago.expediente_id, Pago.id, Pago.fecha_pago, Pago.monto, Pago.registrado_por)
        .order_by(Pago.id),
        Pago.expediente_id,
    )):
        pagos[f.expediente_id].append(PagoFoto(f.id, f.fecha_pago, f.monto, f.registrado_por))

    expedientes = list(sesion.execute(acotar(
        select(
            Expediente.id, Expediente.codigo, Expediente.monto, Expediente.fecha_orden,
            Expediente.plazo_dias, Expediente.fecha_entrega_real, Expediente.solicitante_id,
            Expediente.descripcion, Expediente.proveedor_id, Expediente.area_id,
            Expediente.fecha_requerimiento, Expediente.fecha_inicio_prestacion,
            Expediente.conformidad_plazo_especial,
            Proveedor.razon_social,
        ).join(Proveedor, Proveedor.id == Expediente.proveedor_id)
        .order_by(Expediente.id),
        Expediente.id,
    )))
    previos = _previos_mismo_proveedor(sesion, expedientes, expediente_ids is None)

    return [
        FotoExpediente(
            expediente_id=x.id, codigo=x.codigo, monto=x.monto, fecha_orden=x.fecha_orden,
            plazo_dias=x.plazo_dias, fecha_entrega_real=x.fecha_entrega_real,
            solicitante_id=x.solicitante_id, conformidad=conformidades.get(x.id),
            entregables=tuple(entregables.get(x.id, ())), pagos=tuple(pagos.get(x.id, ())),
            descripcion=x.descripcion, proveedor_id=x.proveedor_id, proveedor=x.razon_social,
            fecha_requerimiento=x.fecha_requerimiento,
            fecha_inicio_prestacion=x.fecha_inicio_prestacion,
            conformidad_plazo_especial=x.conformidad_plazo_especial,
            previos_mismo_proveedor=previos.get(x.id, ()),
        )
        for x in expedientes
    ]


def _previos_mismo_proveedor(sesion: Session, objetivos, todos: bool) -> dict[int, tuple[VecinoFoto, ...]]:
    """Para cada expediente, los del mismo proveedor y área con (fecha de orden, id)
    anterior y a no más de la ventana máxima de días. Las reglas entre expedientes
    (R6, R7) necesitan ver más allá de los expedientes que se evalúan."""
    if not objetivos:
        return {}
    consulta = select(
        Expediente.id, Expediente.codigo, Expediente.monto, Expediente.fecha_orden,
        Expediente.descripcion, Expediente.proveedor_id, Expediente.area_id,
    )
    if not todos:
        pares = {(x.proveedor_id, x.area_id) for x in objetivos}
        consulta = consulta.where(tuple_(Expediente.proveedor_id, Expediente.area_id).in_(pares))
    grupos = defaultdict(list)
    for f in sesion.execute(consulta):
        grupos[f.proveedor_id, f.area_id].append(f)
    maximo = normativa.VENTANA_MAXIMA_ENTRE_EXPEDIENTES_DIAS
    resultado = {}
    for x in objetivos:
        resultado[x.id] = tuple(
            VecinoFoto(v.id, v.codigo, v.fecha_orden, v.monto, v.descripcion)
            for v in sorted(grupos[x.proveedor_id, x.area_id], key=lambda v: (v.fecha_orden, v.id))
            if (v.fecha_orden, v.id) < (x.fecha_orden, x.id)
            and (x.fecha_orden - v.fecha_orden).days <= maximo
        )
    return resultado


def sincronizar(
    sesion: Session,
    expediente_ids: list[int] | None = None,
    *,
    ts_de: Callable[[FotoExpediente, AlertaPropuesta], datetime] | None = None,
    registrar: bool = True,
) -> list[dict]:
    """Evalúa las reglas y crea o actualiza alertas. Devuelve los eventos de bitácora.

    `ts_de` fija el momento de cada alerta (lo usa la siembra, para que los
    datos sean reproducibles). Con `registrar=False` los eventos no se escriben:
    quien llama los encadena junto con los suyos.
    """
    if expediente_ids is not None and not expediente_ids:
        return []
    consulta = select(Alerta)
    if expediente_ids is not None:
        consulta = consulta.where(Alerta.expediente_id.in_(expediente_ids))
    existentes = {(a.expediente_id, a.regla, a.clave): a
                  for a in sesion.execute(consulta).scalars()}

    ahora = datetime.now(timezone.utc)
    eventos, nuevas = [], []
    for foto in cargar_fotos(sesion, expediente_ids):
        for p in evaluar(foto):
            ts = ts_de(foto, p) if ts_de else ahora
            actual = existentes.get((foto.expediente_id, p.regla, p.clave))
            if actual is None:
                alerta = Alerta(
                    expediente_id=foto.expediente_id, regla=p.regla, clave=p.clave,
                    severidad=normativa.SEVERIDAD_POR_REGLA[p.regla],
                    explicacion=p.explicacion, datos=p.datos,
                    persona_implicada_id=p.persona_implicada_id,
                    estado=ESTADO_ABIERTA, creada_en=ts, actualizada_en=ts,
                )
                sesion.add(alerta)
                nuevas.append((alerta, ts))
            elif actual.estado != ESTADO_CERRADA and actual.explicacion != p.explicacion:
                actual.explicacion = p.explicacion
                actual.datos = p.datos
                actual.persona_implicada_id = p.persona_implicada_id
                actual.actualizada_en = ts
                eventos.append(_evento("alerta.actualizada", actual, ts))
    sesion.flush()  # asigna los id de las alertas nuevas
    eventos.extend(_evento("alerta.generada", alerta, ts) for alerta, ts in nuevas)
    if registrar:
        bitacora.registrar_lote(sesion, eventos)
    return eventos


def _evento(accion: str, alerta: Alerta, ts: datetime) -> dict:
    return {
        "ts": ts,
        "actor_id": None,  # la genera el sistema
        "accion": accion,
        "entidad": "alerta",
        "entidad_id": alerta.id,
        "expediente_id": alerta.expediente_id,
        "detalle": {
            "regla": alerta.regla,
            "severidad": alerta.severidad,
            "resumen": f"{alerta.regla} · {alerta.explicacion}",
        },
    }
