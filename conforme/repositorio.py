"""Única puerta de lectura y escritura de la aplicación.

Toda función recibe el `actor` y aplica su alcance en la consulta. Las páginas
no usan SQLAlchemy directamente.
"""
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session, aliased

from conforme import bitacora, evidencias
from conforme import entregables as validacion_entregables
from conforme.errores import ErrorValidacion
from conforme.modelos import (
    ESTADO_ABIERTA, ESTADO_CERRADA, ESTADO_CON_DESCARGO, ESTADO_ESCALADA,
    ROL_AREA_USUARIA, ROL_AUDITOR, ROL_TESORERIA,
    Alerta, AlertaRevision, Area, Bitacora, Conformidad, ConformidadEntregable,
    Entregable, Evidencia, Expediente, Pago, Persona, Proveedor,
)
from conforme.normativa import SEVERIDAD_ALTA, SEVERIDAD_MEDIA
from conforme.permisos import Actor, PermisoDenegado, exigir_rol, filtro_expedientes
from conforme.reglas import motor, semaforo


def _nombre(persona=Persona):
    """Nombre completo, o NULL si no hay persona (p. ej. acciones del sistema)."""
    return func.nullif(func.btrim(func.concat(persona.nombres, " ", persona.apellidos)), "")


_NOMBRE_PERSONA = _nombre()


def _alertas_sin_cerrar(severidad: str):
    return (
        select(func.count())
        .where(
            Alerta.expediente_id == Expediente.id,
            Alerta.severidad == severidad,
            Alerta.estado != ESTADO_CERRADA,
        )
        .correlate(Expediente)
        .scalar_subquery()
    )


def _fila_expediente(fila) -> dict:
    datos = dict(fila._mapping)
    datos["semaforo"] = semaforo.calcular(datos["alertas_altas"], datos["alertas_medias"])
    return datos


def _consulta_expedientes(actor: Actor):
    return (
        select(
            Expediente.id,
            Expediente.codigo,
            Expediente.tipo,
            Expediente.descripcion,
            Area.sigla.label("area_sigla"),
            Area.nombre.label("area"),
            Proveedor.razon_social.label("proveedor"),
            Proveedor.ruc.label("proveedor_ruc"),
            _NOMBRE_PERSONA.label("solicitante"),
            Expediente.solicitante_id,
            Expediente.numero_orden,
            Expediente.fecha_requerimiento,
            Expediente.fecha_orden,
            Expediente.fecha_inicio_prestacion,
            Expediente.plazo_dias,
            Expediente.fecha_entrega_real,
            Expediente.monto,
            exists().where(Conformidad.expediente_id == Expediente.id).label("tiene_conformidad"),
            _alertas_sin_cerrar(SEVERIDAD_ALTA).label("alertas_altas"),
            _alertas_sin_cerrar(SEVERIDAD_MEDIA).label("alertas_medias"),
        )
        .join(Area, Area.id == Expediente.area_id)
        .join(Proveedor, Proveedor.id == Expediente.proveedor_id)
        .join(Persona, Persona.id == Expediente.solicitante_id)
        .where(filtro_expedientes(actor))
    )


def listar_expedientes(sesion: Session, actor: Actor, texto: str | None = None) -> list[dict]:
    consulta = _consulta_expedientes(actor)
    if texto and texto.strip():
        patron = f"%{texto.strip()}%"
        consulta = consulta.where(
            or_(
                Expediente.codigo.ilike(patron),
                Expediente.descripcion.ilike(patron),
                Proveedor.razon_social.ilike(patron),
            )
        )
    filas = sesion.execute(consulta.order_by(Expediente.fecha_orden.desc(), Expediente.id.desc()))
    return [_fila_expediente(f) for f in filas]


def obtener_expediente(sesion: Session, actor: Actor, expediente_id: int) -> dict | None:
    """Devuelve None tanto si no existe como si está fuera del alcance del actor."""
    fila = sesion.execute(
        _consulta_expedientes(actor).where(Expediente.id == expediente_id)
    ).first()
    return _fila_expediente(fila) if fila else None


def linea_de_tiempo(sesion: Session, actor: Actor, expediente_id: int) -> list[dict]:
    """Quién hizo qué, cuándo y con qué documento, en orden cronológico."""
    if obtener_expediente(sesion, actor, expediente_id) is None:
        raise PermisoDenegado("Expediente inexistente o fuera de tu alcance.")
    filas = sesion.execute(
        select(
            Bitacora.id,
            Bitacora.ts,
            Bitacora.accion,
            Bitacora.detalle,
            Bitacora.documento_sha256,
            _NOMBRE_PERSONA.label("actor"),
        )
        .outerjoin(Persona, Persona.id == Bitacora.actor_id)
        .where(Bitacora.expediente_id == expediente_id)
        .order_by(Bitacora.id)
    )
    return [dict(f._mapping) for f in filas]


def listar_bitacora(sesion: Session, actor: Actor, limite: int = 200) -> list[dict]:
    """Últimos registros de la bitácora completa. Solo auditor."""
    exigir_rol(actor, ROL_AUDITOR)
    filas = sesion.execute(
        select(
            Bitacora.id,
            Bitacora.ts,
            _NOMBRE_PERSONA.label("actor"),
            Bitacora.accion,
            Expediente.codigo.label("expediente"),
            Bitacora.documento_sha256,
            Bitacora.hash_anterior,
            Bitacora.hash,
        )
        .outerjoin(Persona, Persona.id == Bitacora.actor_id)
        .outerjoin(Expediente, Expediente.id == Bitacora.expediente_id)
        .order_by(Bitacora.id.desc())
        .limit(limite)
    )
    return [dict(f._mapping) for f in filas]


def verificar_integridad(sesion: Session, actor: Actor) -> bitacora.ResultadoVerificacion:
    """Recalcula toda la cadena de la bitácora. Solo auditor."""
    exigir_rol(actor, ROL_AUDITOR)
    return bitacora.verificar_cadena(sesion)


# --- F2: alta de expedientes --------------------------------------------------

def _expediente_en_alcance(sesion: Session, actor: Actor, expediente_id: int) -> Expediente:
    expediente = sesion.execute(
        select(Expediente).where(Expediente.id == expediente_id, filtro_expedientes(actor))
    ).scalar_one_or_none()
    if expediente is None:
        raise PermisoDenegado("Expediente inexistente o fuera de tu alcance.")
    return expediente


def _monto(valor, nombre: str, *, permite_cero: bool) -> Decimal:
    try:
        monto = Decimal(str(valor)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise ErrorValidacion(f"{nombre}: no es un monto válido.") from None
    if monto < 0 or (monto == 0 and not permite_cero):
        raise ErrorValidacion(
            f"{nombre}: debe ser mayor {'o igual ' if permite_cero else ''}que cero.")
    return monto


def listar_proveedores(sesion: Session, actor: Actor) -> list[dict]:
    filas = sesion.execute(
        select(Proveedor.id, Proveedor.ruc, Proveedor.razon_social)
        .order_by(Proveedor.razon_social)
    )
    return [dict(f._mapping) for f in filas]


def crear_expediente(
    sesion: Session, actor: Actor, *, tipo: str, descripcion: str, proveedor_id: int,
    numero_orden: str, fecha_requerimiento: date, fecha_orden: date,
    fecha_inicio_prestacion: date | None, plazo_dias: int, monto,
    entregables: list[dict], origen_entregables: str = "manual",
) -> int:
    """Alta de un expediente del área del actor, con sus entregables. Solo área usuaria."""
    exigir_rol(actor, ROL_AREA_USUARIA)
    descripcion, numero_orden = (descripcion or "").strip(), (numero_orden or "").strip()
    if tipo not in ("bien", "servicio"):
        raise ErrorValidacion("El tipo debe ser «bien» o «servicio».")
    if not descripcion:
        raise ErrorValidacion("Falta la descripción del expediente.")
    if not numero_orden:
        raise ErrorValidacion("Falta el número de la orden.")
    if fecha_orden < fecha_requerimiento:
        raise ErrorValidacion("La fecha de la orden no puede ser anterior al requerimiento.")
    if fecha_inicio_prestacion and fecha_inicio_prestacion < fecha_orden:
        raise ErrorValidacion("El inicio de la prestación no puede ser anterior a la orden.")
    if not isinstance(plazo_dias, int) or plazo_dias <= 0:
        raise ErrorValidacion("El plazo debe ser un número entero de días mayor que cero.")
    monto = _monto(monto, "Monto", permite_cero=False)
    if origen_entregables not in ("manual", "csv"):
        raise ErrorValidacion("Origen de entregables no admitido.")
    if sesion.get(Proveedor, proveedor_id) is None:
        raise ErrorValidacion("El proveedor elegido no existe.")
    limpios, errores = validacion_entregables.validar(entregables)
    if errores:
        raise ErrorValidacion("Entregables: " + " ".join(errores))

    prefijo = f"EXP-{fecha_requerimiento.year}-"
    ultimo = sesion.execute(
        select(func.max(Expediente.codigo)).where(Expediente.codigo.like(prefijo + "%"))
    ).scalar_one_or_none()
    codigo = f"{prefijo}{(int(ultimo[len(prefijo):]) if ultimo else 0) + 1:04d}"

    expediente = Expediente(
        codigo=codigo, tipo=tipo, descripcion=descripcion, area_id=actor.area_id,
        proveedor_id=proveedor_id, solicitante_id=actor.persona_id, numero_orden=numero_orden,
        fecha_requerimiento=fecha_requerimiento, fecha_orden=fecha_orden,
        fecha_inicio_prestacion=fecha_inicio_prestacion, plazo_dias=plazo_dias,
        fecha_entrega_real=None, monto=monto, creado_en=datetime.now(timezone.utc),
    )
    sesion.add(expediente)
    sesion.flush()
    sesion.add_all(
        Entregable(expediente_id=expediente.id, numero=e["numero"],
                   descripcion=e["descripcion"], origen=origen_entregables)
        for e in limpios
    )
    sesion.flush()
    bitacora.registrar(
        sesion, actor_id=actor.persona_id, accion="expediente.registrado",
        entidad="expediente", entidad_id=expediente.id, expediente_id=expediente.id,
        detalle={
            "codigo": codigo, "monto": monto, "plazo_dias": plazo_dias,
            "numero_orden": numero_orden, "entregables": len(limpios),
            "origen_entregables": origen_entregables,
            "resumen": f"{len(limpios)} entregables cargados ({origen_entregables}).",
        },
    )
    return expediente.id


# --- F2: entregables, conformidad y evidencias --------------------------------

def listar_entregables(sesion: Session, actor: Actor, expediente_id: int) -> list[dict]:
    """Entregables con su estado en la conformidad y sus evidencias (sin el contenido)."""
    _expediente_en_alcance(sesion, actor, expediente_id)
    entregables = [
        {**dict(f._mapping), "evidencias": []}
        for f in sesion.execute(
            select(
                Entregable.id, Entregable.numero, Entregable.descripcion, Entregable.origen,
                ConformidadEntregable.id.label("conformidad_entregable_id"),
                ConformidadEntregable.cumplido, ConformidadEntregable.observacion,
            )
            .outerjoin(ConformidadEntregable, ConformidadEntregable.entregable_id == Entregable.id)
            .where(Entregable.expediente_id == expediente_id)
            .order_by(Entregable.numero)
        )
    ]
    por_ce = {e["conformidad_entregable_id"]: e for e in entregables
              if e["conformidad_entregable_id"] is not None}
    if por_ce:
        for f in sesion.execute(
            select(
                Evidencia.id, Evidencia.conformidad_entregable_id, Evidencia.nombre_archivo,
                Evidencia.mime, Evidencia.tamano, Evidencia.sha256,
            )
            .where(Evidencia.conformidad_entregable_id.in_(por_ce))
            .order_by(Evidencia.id)
        ):
            por_ce[f.conformidad_entregable_id]["evidencias"].append(dict(f._mapping))
    return entregables


def obtener_conformidad(sesion: Session, actor: Actor, expediente_id: int) -> dict | None:
    _expediente_en_alcance(sesion, actor, expediente_id)
    fila = sesion.execute(
        select(
            Conformidad.id, Conformidad.conformante_id, _NOMBRE_PERSONA.label("conformante"),
            Conformidad.fecha_conformidad, Conformidad.observaciones,
            Conformidad.penalidad_aplicada, Conformidad.registrada_en,
        )
        .join(Persona, Persona.id == Conformidad.conformante_id)
        .where(Conformidad.expediente_id == expediente_id)
    ).first()
    return dict(fila._mapping) if fila else None


def obtener_evidencia(sesion: Session, actor: Actor, evidencia_id: int) -> dict | None:
    """Archivo de una evidencia. None si no existe o está fuera del alcance del actor."""
    fila = sesion.execute(
        select(Evidencia.nombre_archivo, Evidencia.mime, Evidencia.sha256, Evidencia.contenido)
        .join(ConformidadEntregable,
              ConformidadEntregable.id == Evidencia.conformidad_entregable_id)
        .join(Conformidad, Conformidad.id == ConformidadEntregable.conformidad_id)
        .join(Expediente, Expediente.id == Conformidad.expediente_id)
        .where(Evidencia.id == evidencia_id, filtro_expedientes(actor))
    ).first()
    return dict(fila._mapping) if fila else None


def registrar_conformidad(
    sesion: Session, actor: Actor, expediente_id: int, *, fecha_conformidad: date,
    penalidad_aplicada, items: list[dict], observaciones: str = "",
    fecha_entrega_real: date | None = None,
) -> int:
    """Registra la conformidad (una por expediente). Solo área usuaria.

    `items`: uno por entregable, con entregable_id, cumplido, observacion y
    evidencias (lista de dict con nombre_archivo, mime, contenido).
    Se puede guardar con entregables sin evidencia: el sistema no bloquea,
    alerta (R1). `fecha_entrega_real` solo se usa si el expediente no la tiene.
    """
    exigir_rol(actor, ROL_AREA_USUARIA)
    expediente = _expediente_en_alcance(sesion, actor, expediente_id)
    if sesion.execute(
        select(Conformidad.id).where(Conformidad.expediente_id == expediente.id)
    ).first():
        raise ErrorValidacion("Este expediente ya tiene una conformidad registrada.")
    entregables = sesion.execute(
        select(Entregable).where(Entregable.expediente_id == expediente.id)
        .order_by(Entregable.numero)
    ).scalars().all()
    if not entregables:
        raise ErrorValidacion(
            "El expediente no tiene entregables: no hay sobre qué dar conformidad.")
    por_id = {i["entregable_id"]: i for i in items}
    if set(por_id) != {e.id for e in entregables} or len(por_id) != len(items):
        raise ErrorValidacion("Debes indicar el estado de cada entregable del expediente.")
    penalidad = _monto(penalidad_aplicada, "Penalidad aplicada", permite_cero=True)
    entrega = expediente.fecha_entrega_real or fecha_entrega_real
    if entrega is None:
        raise ErrorValidacion("Falta la fecha de entrega real.")
    if entrega < expediente.fecha_orden:
        raise ErrorValidacion("La entrega no puede ser anterior a la orden.")
    if fecha_conformidad < entrega:
        raise ErrorValidacion("La conformidad no puede tener fecha anterior a la entrega.")
    # Se valida todo antes de escribir nada.
    archivos = {
        e.id: [evidencias.preparar(a["nombre_archivo"], a["mime"], a["contenido"])
               for a in por_id[e.id].get("evidencias") or []]
        for e in entregables
    }

    ahora = datetime.now(timezone.utc)
    expediente.fecha_entrega_real = entrega
    conformidad = Conformidad(
        expediente_id=expediente.id, conformante_id=actor.persona_id,
        fecha_conformidad=fecha_conformidad, observaciones=(observaciones or "").strip(),
        penalidad_aplicada=penalidad, registrada_en=ahora,
    )
    sesion.add(conformidad)
    sesion.flush()
    cumplidos = sum(1 for i in items if i["cumplido"])
    eventos = [{
        "ts": ahora, "actor_id": actor.persona_id, "accion": "conformidad.registrada",
        "entidad": "conformidad", "entidad_id": conformidad.id, "expediente_id": expediente.id,
        "detalle": {
            "fecha_conformidad": fecha_conformidad, "fecha_entrega_real": entrega,
            "penalidad_aplicada": penalidad, "entregables": len(entregables),
            "entregables_cumplidos": cumplidos,
            "resumen": f"{cumplidos} de {len(entregables)} entregables dados por cumplidos.",
        },
    }]
    for e in entregables:
        item = por_id[e.id]
        ce = ConformidadEntregable(
            conformidad_id=conformidad.id, entregable_id=e.id,
            cumplido=bool(item["cumplido"]), observacion=(item.get("observacion") or "").strip(),
        )
        sesion.add(ce)
        sesion.flush()
        for archivo in archivos[e.id]:
            evidencia = Evidencia(
                conformidad_entregable_id=ce.id, subido_por=actor.persona_id,
                subido_en=ahora, **archivo,
            )
            sesion.add(evidencia)
            sesion.flush()
            eventos.append({
                "ts": ahora, "actor_id": actor.persona_id, "accion": "evidencia.adjuntada",
                "entidad": "evidencia", "entidad_id": evidencia.id,
                "expediente_id": expediente.id,
                "detalle": {"documento": archivo["nombre_archivo"], "entregable": e.numero},
                "documento_sha256": archivo["sha256"],
            })
    bitacora.registrar_lote(sesion, eventos)
    motor.sincronizar(sesion, [expediente.id])
    return conformidad.id


# --- F2: pagos ----------------------------------------------------------------

def listar_pagos(sesion: Session, actor: Actor, expediente_id: int) -> list[dict]:
    _expediente_en_alcance(sesion, actor, expediente_id)
    filas = sesion.execute(
        select(
            Pago.id, Pago.fecha_pago, Pago.monto, Pago.penalidad_descontada,
            _NOMBRE_PERSONA.label("registrado_por"), Pago.registrado_en,
        )
        .join(Persona, Persona.id == Pago.registrado_por)
        .where(Pago.expediente_id == expediente_id)
        .order_by(Pago.id)
    )
    return [dict(f._mapping) for f in filas]


def registrar_pago(
    sesion: Session, actor: Actor, expediente_id: int, *, fecha_pago: date, monto,
    penalidad_descontada=0,
) -> int:
    """Registra un pago. Solo tesorería. No se bloquea: si falta conformidad, alerta (R5)."""
    exigir_rol(actor, ROL_TESORERIA)
    expediente = _expediente_en_alcance(sesion, actor, expediente_id)
    monto = _monto(monto, "Monto pagado", permite_cero=False)
    penalidad = _monto(penalidad_descontada, "Penalidad descontada", permite_cero=True)
    if fecha_pago < expediente.fecha_orden:
        raise ErrorValidacion("El pago no puede ser anterior a la orden.")
    pago = Pago(
        expediente_id=expediente.id, fecha_pago=fecha_pago, monto=monto,
        penalidad_descontada=penalidad, registrado_por=actor.persona_id,
        registrado_en=datetime.now(timezone.utc),
    )
    sesion.add(pago)
    sesion.flush()
    bitacora.registrar(
        sesion, actor_id=actor.persona_id, accion="pago.registrado", entidad="pago",
        entidad_id=pago.id, expediente_id=expediente.id,
        detalle={"fecha_pago": fecha_pago, "monto": monto, "penalidad_descontada": penalidad},
    )
    motor.sincronizar(sesion, [expediente.id])
    return pago.id


def reevaluar(sesion: Session, actor: Actor, expediente_id: int) -> int:
    """Vuelve a pasar las reglas por el expediente. Devuelve cuántas alertas nuevas hubo."""
    exigir_rol(actor, ROL_AREA_USUARIA, ROL_TESORERIA)
    expediente = _expediente_en_alcance(sesion, actor, expediente_id)
    eventos = motor.sincronizar(sesion, [expediente.id])
    return sum(1 for e in eventos if e["accion"] == "alerta.generada")


# --- F2: alertas --------------------------------------------------------------

def listar_alertas(
    sesion: Session, actor: Actor, *, expediente_id: int | None = None,
) -> list[dict]:
    """Alertas de los expedientes que el actor puede ver; las más recientes primero."""
    implicada = aliased(Persona)
    consulta = (
        select(
            Alerta.id, Alerta.regla, Alerta.clave, Alerta.severidad, Alerta.explicacion,
            Alerta.datos, Alerta.estado, Alerta.creada_en, Alerta.actualizada_en,
            Alerta.expediente_id, Expediente.codigo.label("expediente"),
            Area.sigla.label("area_sigla"), Alerta.persona_implicada_id,
            _nombre(implicada).label("implicado"),
            Conformidad.conformante_id,
        )
        .join(Expediente, Expediente.id == Alerta.expediente_id)
        .join(Area, Area.id == Expediente.area_id)
        .outerjoin(implicada, implicada.id == Alerta.persona_implicada_id)
        .outerjoin(Conformidad, Conformidad.expediente_id == Expediente.id)
        .where(filtro_expedientes(actor))
    )
    if expediente_id is not None:
        consulta = consulta.where(Alerta.expediente_id == expediente_id)
    filas = sesion.execute(consulta.order_by(Alerta.creada_en.desc(), Alerta.id.desc()))
    return [dict(f._mapping) for f in filas]


def _alerta_en_alcance(sesion: Session, actor: Actor, alerta_id: int) -> Alerta:
    alerta = sesion.execute(
        select(Alerta)
        .join(Expediente, Expediente.id == Alerta.expediente_id)
        .where(Alerta.id == alerta_id, filtro_expedientes(actor))
    ).scalar_one_or_none()
    if alerta is None:
        raise PermisoDenegado("Alerta inexistente o fuera de tu alcance.")
    return alerta


def revisiones_de_alerta(sesion: Session, actor: Actor, alerta_id: int) -> list[dict]:
    """Descargos, cierres y escalamientos de una alerta, en orden."""
    _alerta_en_alcance(sesion, actor, alerta_id)
    filas = sesion.execute(
        select(AlertaRevision.tipo, _NOMBRE_PERSONA.label("autor"),
               AlertaRevision.texto, AlertaRevision.creado_en)
        .join(Persona, Persona.id == AlertaRevision.autor_id)
        .where(AlertaRevision.alerta_id == alerta_id)
        .order_by(AlertaRevision.id)
    )
    return [dict(f._mapping) for f in filas]


_ACCION_POR_REVISION = {
    "descargo": "alerta.descargo",
    "cierre": "alerta.cerrada",
    "escalamiento": "alerta.escalada",
}


def _revisar(sesion: Session, actor: Actor, alerta: Alerta, tipo: str, texto: str,
             nuevo_estado: str) -> None:
    ahora = datetime.now(timezone.utc)
    alerta.estado = nuevo_estado
    alerta.actualizada_en = ahora
    sesion.add(AlertaRevision(alerta_id=alerta.id, tipo=tipo, autor_id=actor.persona_id,
                              texto=texto, creado_en=ahora))
    sesion.flush()
    bitacora.registrar(
        sesion, ts=ahora, actor_id=actor.persona_id, accion=_ACCION_POR_REVISION[tipo],
        entidad="alerta", entidad_id=alerta.id, expediente_id=alerta.expediente_id,
        detalle={"regla": alerta.regla, "estado": nuevo_estado, "texto": texto,
                 "resumen": f"{alerta.regla} · {texto}"},
    )


def _texto_obligatorio(texto: str, nombre: str) -> str:
    texto = (texto or "").strip()
    if not texto:
        raise ErrorValidacion(f"{nombre} es obligatorio.")
    return texto


def registrar_descargo(sesion: Session, actor: Actor, alerta_id: int, texto: str) -> None:
    """Descargo de la persona implicada o de quien dio la conformidad."""
    alerta = _alerta_en_alcance(sesion, actor, alerta_id)
    conformante_id = sesion.execute(
        select(Conformidad.conformante_id)
        .where(Conformidad.expediente_id == alerta.expediente_id)
    ).scalar_one_or_none()
    if actor.persona_id not in (alerta.persona_implicada_id, conformante_id):
        raise PermisoDenegado(
            "Solo la persona implicada o quien dio la conformidad puede presentar un descargo.")
    texto = _texto_obligatorio(texto, "El descargo")
    if alerta.estado == ESTADO_CERRADA:
        raise ErrorValidacion("La alerta ya está cerrada.")
    nuevo = ESTADO_CON_DESCARGO if alerta.estado == ESTADO_ABIERTA else alerta.estado
    _revisar(sesion, actor, alerta, "descargo", texto, nuevo)


def _exigir_revisor(sesion: Session, actor: Actor, alerta_id: int) -> Alerta:
    exigir_rol(actor, ROL_TESORERIA, ROL_AUDITOR)
    alerta = _alerta_en_alcance(sesion, actor, alerta_id)
    if alerta.persona_implicada_id == actor.persona_id:
        raise PermisoDenegado(
            "No puedes cerrar ni escalar una alerta en la que figuras como persona implicada.")
    return alerta


def cerrar_alerta(sesion: Session, actor: Actor, alerta_id: int, motivo: str) -> None:
    """Cierre con motivo obligatorio. Tesorería o auditor, nunca la persona implicada."""
    alerta = _exigir_revisor(sesion, actor, alerta_id)
    motivo = _texto_obligatorio(motivo, "El motivo")
    if alerta.estado == ESTADO_CERRADA:
        raise ErrorValidacion("La alerta ya está cerrada.")
    _revisar(sesion, actor, alerta, "cierre", motivo, ESTADO_CERRADA)


def escalar_alerta(sesion: Session, actor: Actor, alerta_id: int, motivo: str) -> None:
    """Escalamiento con motivo obligatorio. Tesorería o auditor, nunca la persona implicada."""
    alerta = _exigir_revisor(sesion, actor, alerta_id)
    motivo = _texto_obligatorio(motivo, "El motivo")
    if alerta.estado in (ESTADO_CERRADA, ESTADO_ESCALADA):
        raise ErrorValidacion("La alerta ya está cerrada o escalada.")
    _revisar(sesion, actor, alerta, "escalamiento", motivo, ESTADO_ESCALADA)
