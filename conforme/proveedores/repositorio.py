"""Evaluación de posibles proveedores de un expediente (Fase 2). Única puerta a sus datos.

Flujo (estado del expediente entre paréntesis):
1. Abastecimiento analiza a cada postor por seis dimensiones   (en_evaluacion_proveedores)
2. Consolida, selecciona con sustento, justifica cada descarte y declara no tener conflicto
   de intereses; lo envía a revisión independiente           (pendiente_revision_independiente)
3. Otro especialista de Abastecimiento la aprueba              (seleccion_aprobada)
   o la observa, y vuelve al paso 1                            (en_evaluacion_proveedores)
4. El área usuaria confirma la orden sobre el proveedor aprobado (en_ejecucion)

Quien evalúa nunca hace la revisión independiente: se controla aquí y en la base.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from conforme import bitacora
from conforme import repositorio as expedientes
from conforme.errores import ErrorValidacion
from conforme.modelos import (
    ROL_ABASTECIMIENTO, ROL_AREA_USUARIA, Alerta, Area, Bitacora, Conformidad, ConflictoInteres,
    Expediente, ExpedientePostor, Persona, Proveedor, RevisionPrevia, Usuario,
)
from conforme.permisos import (
    ROLES_EVALUACION_LECTURA, Actor, PermisoDenegado, exigir_otra_persona, exigir_rol,
)
from conforme.prevencion.esquemas import ruc_valido
from conforme.proveedores import consolidado, dimensiones, fuentes
from conforme.proveedores.dimensiones import DIMENSIONES, Contexto, Funcionario, Historial, Postor
from conforme.reglas import motor

EN_EVALUACION = "en_evaluacion_proveedores"
EN_REVISION = "pendiente_revision_independiente"
APROBADA = "seleccion_aprobada"
ESTADOS_PREVIOS_A_LA_ORDEN = ("requerimiento", "tdr_observado", EN_EVALUACION, EN_REVISION, APROBADA)
MAXIMO_POSTORES = 8


def _ahora():
    return datetime.now(timezone.utc)


def _texto(valor: str | None, nombre: str, maximo: int = 2000, obligatorio: bool = True) -> str | None:
    valor = (valor or "").strip()
    if not valor:
        if obligatorio:
            raise ErrorValidacion(f"{nombre} es obligatorio.")
        return None
    if len(valor) > maximo:
        raise ErrorValidacion(f"{nombre} admite hasta {maximo} caracteres.")
    return valor


def _expediente(sesion: Session, actor: Actor, expediente_id: int, *, bloquear=False) -> Expediente:
    return expedientes._expediente_en_alcance(sesion, actor, expediente_id, bloquear=bloquear)


def _evaluacion(sesion: Session, expediente_id: int) -> RevisionPrevia | None:
    return sesion.scalar(select(RevisionPrevia).where(RevisionPrevia.expediente_id == expediente_id))


def _postores(sesion: Session, expediente_id: int) -> list[ExpedientePostor]:
    return list(sesion.scalars(select(ExpedientePostor)
                               .where(ExpedientePostor.expediente_id == expediente_id)
                               .order_by(ExpedientePostor.id)))


def _nombre_usuario(sesion: Session, usuario_id: int | None) -> str | None:
    if usuario_id is None:
        return None
    fila = sesion.execute(select(Persona.nombres, Persona.apellidos)
                          .join(Usuario, Usuario.persona_id == Persona.id)
                          .where(Usuario.id == usuario_id)).first()
    return f"{fila.nombres} {fila.apellidos}" if fila else None


def _registrar(sesion, actor, expediente_id, accion, resumen, **detalle):
    bitacora.registrar(sesion, actor_id=actor.persona_id, accion=accion, entidad="expediente",
                       entidad_id=expediente_id, expediente_id=expediente_id,
                       detalle={**detalle, "resumen": resumen})


def _editable(sesion: Session, actor: Actor, expediente: Expediente) -> RevisionPrevia | None:
    """Solo Abastecimiento, solo en evaluación y solo quien conduce la evaluación."""
    exigir_rol(actor, ROL_ABASTECIMIENTO)
    if expediente.estado_flujo == EN_REVISION:
        raise ErrorValidacion("La evaluación está en revisión independiente: no se puede modificar.")
    if expediente.estado_flujo != EN_EVALUACION:
        raise ErrorValidacion("Este expediente ya no está en evaluación de proveedores.")
    evaluacion = _evaluacion(sesion, expediente.id)
    if evaluacion and evaluacion.evaluador_id != actor.usuario_id:
        raise PermisoDenegado(
            f"Esta evaluación la conduce {_nombre_usuario(sesion, evaluacion.evaluador_id)}. "
            "Tú puedes hacer la revisión independiente cuando te la envíe.")
    return evaluacion


def _asegurar_evaluacion(sesion: Session, actor: Actor, expediente: Expediente) -> RevisionPrevia:
    evaluacion = _editable(sesion, actor, expediente)
    if evaluacion is None:
        evaluacion = RevisionPrevia(asignado_id=actor.usuario_id, evaluador_id=actor.usuario_id,
                                    expediente_id=expediente.id, creado_en=_ahora())
        sesion.add(evaluacion)
        sesion.flush()
        _registrar(sesion, actor, expediente.id, "evaluacion.iniciada",
                   f"{actor.nombre} inició la evaluación de proveedores.")
    return evaluacion


# --- Lectura ---------------------------------------------------------------------------

def _postor_dict(p: ExpedientePostor, estimado: Decimal) -> dict:
    return {
        "id": p.id, "ruc": p.ruc, "razon_social": p.razon_social, "monto_cotizado": p.monto_cotizado,
        "variacion": float(round((p.monto_cotizado - estimado) / estimado, 4)) if estimado else None,
        "plazo_dias": p.plazo_dias, "contacto_nombre": p.contacto_nombre, "contacto_correo": p.contacto_correo,
        "contacto_telefono": p.contacto_telefono, "direccion": p.direccion, "proforma_ref": p.proforma_ref,
        "estado": p.estado, "motivo_descarte": p.motivo_descarte,
        "dimensiones": p.analisis_dimensiones or {}, "consolidado": p.informe_consolidado,
        "notas": p.notas_encargado, "analizado_en": p.analizado_en, "consolidado_en": p.consolidado_en,
        "analisis_completo": all(c in (p.analisis_dimensiones or {}) for c in DIMENSIONES),
    }


def bandeja(sesion: Session, actor: Actor) -> list[dict]:
    """Expedientes con evaluación de proveedores (en curso o terminada)."""
    exigir_rol(actor, *ROLES_EVALUACION_LECTURA)
    postores = (select(func.count()).where(ExpedientePostor.expediente_id == Expediente.id)
                .correlate(Expediente).scalar_subquery())
    analizados = (select(func.count()).where(ExpedientePostor.expediente_id == Expediente.id,
                                             ExpedientePostor.analizado_en.isnot(None))
                  .correlate(Expediente).scalar_subquery())
    filas = sesion.execute(
        select(Expediente.id, Expediente.codigo, Expediente.descripcion, Expediente.tipo, Expediente.monto,
               Expediente.estado_flujo, Expediente.fecha_requerimiento, Expediente.area_id,
               postores.label("postores"), analizados.label("analizados"),
               RevisionPrevia.evaluador_id, RevisionPrevia.estado_revision_independiente,
               RevisionPrevia.enviado_revision_en, RevisionPrevia.revisor_independiente_id,
               RevisionPrevia.proveedor_seleccionado_ruc)
        .outerjoin(RevisionPrevia, RevisionPrevia.expediente_id == Expediente.id)
        .where((Expediente.estado_flujo.in_(ESTADOS_PREVIOS_A_LA_ORDEN)) | RevisionPrevia.id.isnot(None))
        .order_by(Expediente.fecha_requerimiento.desc(), Expediente.id.desc())
    )
    areas = {a: n for a, n in sesion.execute(select(Area.id, Area.nombre))}
    resultado = []
    for f in filas:
        datos = dict(f._mapping)
        datos["area"] = areas.get(datos.pop("area_id"))
        datos["evaluador"] = _nombre_usuario(sesion, datos["evaluador_id"])
        datos["revisor"] = _nombre_usuario(sesion, datos["revisor_independiente_id"])
        datos["soy_evaluador"] = datos["evaluador_id"] == actor.usuario_id
        datos["me_toca_revisar"] = (actor.rol == ROL_ABASTECIMIENTO and datos["estado_flujo"] == EN_REVISION
                                    and datos["evaluador_id"] != actor.usuario_id)
        resultado.append(datos)
    return resultado


def obtener(sesion: Session, actor: Actor, expediente_id: int) -> dict:
    exigir_rol(actor, *ROLES_EVALUACION_LECTURA)
    expediente = expedientes.obtener_expediente(sesion, actor, expediente_id)
    if expediente is None:
        raise PermisoDenegado("Expediente inexistente o fuera de tu alcance.")
    evaluacion = _evaluacion(sesion, expediente_id)
    postores = [_postor_dict(p, expediente["monto"]) for p in _postores(sesion, expediente_id)]
    estado = expediente["estado_flujo"]
    es_dec = actor.rol == ROL_ABASTECIMIENTO
    evaluador_id = evaluacion.evaluador_id if evaluacion else None
    puede_editar = es_dec and estado == EN_EVALUACION and evaluador_id in (None, actor.usuario_id)
    puede_revisar = es_dec and estado == EN_REVISION and evaluador_id != actor.usuario_id
    if not es_dec:
        bloqueo = "Consulta en solo lectura."
    elif estado == EN_EVALUACION and not puede_editar:
        bloqueo = (f"Esta evaluación la conduce {_nombre_usuario(sesion, evaluador_id)}. "
                   "Podrás hacer la revisión independiente cuando te la envíe.")
    else:
        bloqueo = None
    declaraciones = [dict(f._mapping) for f in sesion.execute(
        select(ConflictoInteres.id, ConflictoInteres.tipo, ConflictoInteres.descripcion,
               ConflictoInteres.bloqueante, ConflictoInteres.estado, ConflictoInteres.proveedor_ruc,
               ConflictoInteres.registrado_en, expedientes._NOMBRE_PERSONA.label("persona"))
        .join(Persona, Persona.id == ConflictoInteres.persona_id)
        .where(ConflictoInteres.expediente_id == expediente_id).order_by(ConflictoInteres.id))]
    return {
        "expediente": expediente,
        "dimensiones": DIMENSIONES,
        "veredictos": consolidado.VEREDICTOS,
        "postores": postores,
        "evaluacion": None if evaluacion is None else {
            "evaluador": _nombre_usuario(sesion, evaluacion.evaluador_id),
            "revisor": _nombre_usuario(sesion, evaluacion.revisor_independiente_id),
            "estado_revision": evaluacion.estado_revision_independiente,
            "comentario_revision": evaluacion.comentario_revision_independiente,
            "enviado_en": evaluacion.enviado_revision_en,
            "revisado_en": evaluacion.revisado_independiente_en,
            "seleccionado_ruc": evaluacion.proveedor_seleccionado_ruc,
            "sustento": evaluacion.sustento_seleccion,
            "iniciada_en": evaluacion.creado_en,
        },
        "declaraciones": declaraciones,
        "puede_editar": puede_editar,
        "puede_revisar": puede_revisar,
        "bloqueo": bloqueo,
        "fuentes_simuladas": fuentes.SIMULADO,
    }


def seleccion(sesion: Session, actor: Actor, expediente_id: int) -> dict | None:
    """Lo que cualquier rol con acceso al expediente puede saber de la selección."""
    _expediente(sesion, actor, expediente_id)
    evaluacion = _evaluacion(sesion, expediente_id)
    postores = _postores(sesion, expediente_id)
    if evaluacion is None and not postores:
        return None
    elegido = next((p for p in postores if evaluacion and p.ruc == evaluacion.proveedor_seleccionado_ruc), None)
    return {
        "postores": len(postores),
        "estado_revision": evaluacion.estado_revision_independiente if evaluacion else None,
        "evaluador": _nombre_usuario(sesion, evaluacion.evaluador_id) if evaluacion else None,
        "revisor": _nombre_usuario(sesion, evaluacion.revisor_independiente_id) if evaluacion else None,
        "comentario_revision": evaluacion.comentario_revision_independiente if evaluacion else None,
        "seleccionado": None if elegido is None else {
            "id": elegido.id, "ruc": elegido.ruc, "razon_social": elegido.razon_social,
            "monto_cotizado": elegido.monto_cotizado, "plazo_dias": elegido.plazo_dias,
            "veredicto": (elegido.informe_consolidado or {}).get("titulo"),
        },
    }


# --- Postores --------------------------------------------------------------------------

def _validar_postor(datos: dict) -> dict:
    ruc = (datos.get("ruc") or "").strip()
    if not ruc_valido(ruc):
        raise ErrorValidacion("El RUC no es válido: revisa sus 11 dígitos y el dígito verificador.")
    try:
        monto = Decimal(str(datos.get("monto_cotizado"))).quantize(Decimal("0.01"))
    except Exception:
        raise ErrorValidacion("El monto cotizado no es válido.") from None
    if monto <= 0:
        raise ErrorValidacion("El monto cotizado debe ser mayor que cero.")
    plazo = datos.get("plazo_dias")
    if not isinstance(plazo, int) or plazo <= 0:
        raise ErrorValidacion("El plazo ofrecido debe ser un número de días mayor que cero.")
    return {
        "ruc": ruc, "razon_social": _texto(datos.get("razon_social"), "La razón social", 200),
        "monto_cotizado": monto, "plazo_dias": plazo,
        "contacto_nombre": _texto(datos.get("contacto_nombre"), "El contacto", 120, False),
        "contacto_correo": _texto(datos.get("contacto_correo"), "El correo", 120, False),
        "contacto_telefono": _texto(datos.get("contacto_telefono"), "El teléfono", 40, False),
        "direccion": _texto(datos.get("direccion"), "La dirección", 200, False),
        "proforma_ref": _texto(datos.get("proforma_ref"), "La referencia de la cotización", 120, False),
    }


def insertar_postores(sesion: Session, actor: Actor, expediente: Expediente, lista: list[dict]) -> list[int]:
    """Uso interno: alta de postores ya autorizada por quien llama."""
    existentes = {p.ruc for p in _postores(sesion, expediente.id)}
    if len(existentes) + len(lista) > MAXIMO_POSTORES:
        raise ErrorValidacion(f"Un expediente admite hasta {MAXIMO_POSTORES} posibles proveedores.")
    ids = []
    for datos in lista:
        limpio = _validar_postor(datos)
        if limpio["ruc"] in existentes:
            raise ErrorValidacion(f"El RUC {limpio['ruc']} ya figura entre los posibles proveedores.")
        existentes.add(limpio["ruc"])
        postor = ExpedientePostor(expediente_id=expediente.id, registrado_por=actor.persona_id,
                                  creado_en=_ahora(), **limpio)
        sesion.add(postor)
        sesion.flush()
        ids.append(postor.id)
    return ids


def agregar_postor(sesion: Session, actor: Actor, expediente_id: int, datos: dict) -> int:
    expediente = _expediente(sesion, actor, expediente_id, bloquear=True)
    _asegurar_evaluacion(sesion, actor, expediente)
    (postor_id,) = insertar_postores(sesion, actor, expediente, [datos])
    _invalidar_consolidado(sesion, expediente_id)
    _registrar(sesion, actor, expediente_id, "postor.agregado",
               f"Posible proveedor agregado: {datos.get('razon_social', '').strip()} (RUC {datos.get('ruc')}).")
    return postor_id


def _postor(sesion: Session, expediente_id: int, postor_id: int) -> ExpedientePostor:
    postor = sesion.get(ExpedientePostor, postor_id)
    if postor is None or postor.expediente_id != expediente_id:
        raise ErrorValidacion("El posible proveedor no pertenece a este expediente.")
    return postor


def quitar_postor(sesion: Session, actor: Actor, expediente_id: int, postor_id: int) -> None:
    expediente = _expediente(sesion, actor, expediente_id, bloquear=True)
    _editable(sesion, actor, expediente)
    postor = _postor(sesion, expediente_id, postor_id)
    sesion.delete(postor)
    sesion.flush()
    _invalidar_consolidado(sesion, expediente_id)
    _registrar(sesion, actor, expediente_id, "postor.retirado",
               f"Posible proveedor retirado: {postor.razon_social} (RUC {postor.ruc}).")


def guardar_notas(sesion: Session, actor: Actor, expediente_id: int, postor_id: int, notas: str) -> None:
    expediente = _expediente(sesion, actor, expediente_id, bloquear=True)
    _editable(sesion, actor, expediente)
    postor = _postor(sesion, expediente_id, postor_id)
    postor.notas_encargado = (_texto(notas, "La nota", 2000, False) or "")


# --- Análisis por dimensiones -----------------------------------------------------------

def _persona_por_usuario(sesion: Session, usuario_id: int) -> Persona | None:
    return sesion.scalar(select(Persona).join(Usuario, Usuario.persona_id == Persona.id)
                         .where(Usuario.id == usuario_id))


def _historial(sesion: Session, ruc: str, hoy: date) -> Historial:
    filas = list(sesion.execute(
        select(Expediente.id, Expediente.codigo, Expediente.fecha_orden)
        .join(Proveedor, Proveedor.id == Expediente.proveedor_id)
        .where(Proveedor.ruc == ruc).order_by(Expediente.fecha_orden.desc())))
    if not filas:
        return Historial()
    ids = [f.id for f in filas]
    con_penalidad = sesion.scalar(select(func.count(func.distinct(Conformidad.expediente_id)))
                                  .where(Conformidad.expediente_id.in_(ids), Conformidad.penalidad_aplicada > 0))
    con_atraso = sesion.scalar(select(func.count(func.distinct(Alerta.expediente_id)))
                               .where(Alerta.expediente_id.in_(ids), Alerta.regla.in_(("R2", "R3")),
                                      Alerta.expediente_id.notin_(
                                          select(Conformidad.expediente_id).where(
                                              Conformidad.expediente_id.in_(ids),
                                              Conformidad.penalidad_aplicada > 0))))
    observados = sesion.scalar(select(func.count()).where(Bitacora.expediente_id.in_(ids),
                                                          Bitacora.accion == "entregable.observado"))
    devueltas = sesion.scalar(select(func.count()).where(Conformidad.expediente_id.in_(ids),
                                                         Conformidad.estado_revision_dec == "devuelta"))
    hace_un_ano = hoy - timedelta(days=365)
    return Historial(
        expedientes=len(filas), con_penalidad=con_penalidad or 0, con_atraso=con_atraso or 0,
        entregables_observados=observados or 0, conformidades_devueltas=devueltas or 0,
        ordenes_12m=sum(1 for f in filas if f.fecha_orden and f.fecha_orden >= hace_un_ano),
        codigos=tuple(f.codigo for f in filas),
    )


def _comparables(sesion: Session, expediente: Expediente) -> tuple[tuple[str, Decimal], ...]:
    propias = dimensiones.palabras(expediente.descripcion)
    if not propias:
        return ()
    resultado = []
    for codigo, descripcion, monto in sesion.execute(
            select(Expediente.codigo, Expediente.descripcion, Expediente.monto)
            .where(Expediente.id != expediente.id, Expediente.fecha_orden.isnot(None),
                   Expediente.tipo == expediente.tipo)):
        otras = dimensiones.palabras(descripcion)
        if otras and len(propias & otras) / len(propias | otras) >= 0.5:
            resultado.append((codigo, monto))
    return tuple(resultado[:20])


def _contexto(sesion: Session, expediente: Expediente, evaluador_id: int, postores, fichas) -> callable:
    hoy = date.today()
    funcionarios = []
    solicitante = sesion.get(Persona, expediente.solicitante_id)
    funcionarios.append(Funcionario(solicitante.dni, f"{solicitante.nombres} {solicitante.apellidos}",
                                    "solicitante del requerimiento"))
    evaluador = _persona_por_usuario(sesion, evaluador_id)
    if evaluador:
        funcionarios.append(Funcionario(evaluador.dni, f"{evaluador.nombres} {evaluador.apellidos}",
                                        "especialista de Abastecimiento que evalúa"))
    sancionadas = fuentes.personas_de_empresas_sancionadas(hoy)
    comparables = _comparables(sesion, expediente)

    def para(postor: ExpedientePostor) -> Contexto:
        return Contexto(
            descripcion=expediente.descripcion, valor_estimado=expediente.monto,
            plazo_dias=expediente.plazo_dias, hoy=hoy, funcionarios=tuple(funcionarios),
            otros=tuple((_postor_puro(o), fichas[o.id]) for o in postores if o.id != postor.id),
            personas_sancionadas=sancionadas, historial=_historial(sesion, postor.ruc, hoy),
            comparables=comparables,
        )
    return para


def _postor_puro(p: ExpedientePostor) -> Postor:
    return Postor(p.id, p.ruc, p.razon_social, p.monto_cotizado, p.plazo_dias,
                  p.contacto_correo, p.contacto_telefono, p.direccion)


def _invalidar_consolidado(sesion: Session, expediente_id: int) -> None:
    for p in _postores(sesion, expediente_id):
        if p.informe_consolidado is not None or p.estado == "consolidado":
            p.informe_consolidado, p.consolidado_en = None, None
            p.estado = "analizado" if p.analizado_en else "pendiente"


def analizar(sesion: Session, actor: Actor, expediente_id: int, *, postor_id: int | None = None,
             dimension: str | None = None) -> dict:
    """Analiza a todos los postores (o a uno) en todas las dimensiones (o en una)."""
    expediente = _expediente(sesion, actor, expediente_id, bloquear=True)
    evaluacion = _asegurar_evaluacion(sesion, actor, expediente)
    if dimension is not None and dimension not in DIMENSIONES:
        raise ErrorValidacion("Elige una dimensión válida.")
    postores = _postores(sesion, expediente_id)
    if not postores:
        raise ErrorValidacion("Agrega al menos un posible proveedor antes de analizar.")
    objetivos = [p for p in postores if postor_id is None or p.id == postor_id]
    if not objetivos:
        raise ErrorValidacion("El posible proveedor no pertenece a este expediente.")
    fichas = {p.id: fuentes.consultar(p.ruc, p.razon_social) for p in postores}
    contexto_de = _contexto(sesion, expediente, evaluacion.evaluador_id, postores, fichas)
    ahora = _ahora()
    conteo = {"limpio": 0, "revisar": 0, "alerta": 0}
    for p in objetivos:
        resultados = dimensiones.evaluar(_postor_puro(p), fichas[p.id], contexto_de(p),
                                         [dimension] if dimension else None)
        for r in resultados.values():
            r["calculado_en"] = ahora.isoformat()
            conteo[r["estado"]] += 1
        p.analisis_dimensiones = {**(p.analisis_dimensiones or {}), **resultados}
        p.analizado_en = ahora
        if p.estado in ("pendiente", "consolidado"):
            p.estado = "analizado"
    _invalidar_consolidado(sesion, expediente_id)
    sesion.flush()
    alcance = (f"{DIMENSIONES[dimension]} de " if dimension else "6 dimensiones de ") + (
        objetivos[0].razon_social if postor_id else f"{len(objetivos)} posible(s) proveedor(es)")
    _registrar(sesion, actor, expediente_id, "evaluacion.analizada",
               f"Análisis de {alcance}: {conteo['alerta']} en alerta, {conteo['revisar']} por revisar, "
               f"{conteo['limpio']} limpias.", dimension=dimension, postor_id=postor_id)
    return conteo


def consolidar(sesion: Session, actor: Actor, expediente_id: int) -> None:
    expediente = _expediente(sesion, actor, expediente_id, bloquear=True)
    _asegurar_evaluacion(sesion, actor, expediente)
    postores = _postores(sesion, expediente_id)
    if not postores:
        raise ErrorValidacion("Agrega y analiza al menos un posible proveedor.")
    incompletos = [p.razon_social for p in postores
                   if not all(c in (p.analisis_dimensiones or {}) for c in DIMENSIONES)]
    if incompletos:
        raise ErrorValidacion("Antes de consolidar, analiza las 6 dimensiones de: " + ", ".join(incompletos) + ".")
    ahora = _ahora()
    veredictos = []
    for p in postores:
        p.informe_consolidado = consolidado.consolidar(p.analisis_dimensiones)
        p.consolidado_en = ahora
        p.estado = "consolidado"
        veredictos.append(f"{p.razon_social}: {p.informe_consolidado['titulo']}")
    sesion.flush()
    _registrar(sesion, actor, expediente_id, "evaluacion.consolidada",
               "Informe consolidado. " + "; ".join(veredictos) + ".")


# --- Selección y revisión independiente -------------------------------------------------

def enviar_a_revision(sesion: Session, actor: Actor, expediente_id: int, *, seleccionado_id: int,
                      sustento: str, descartes: dict[int, str], declaro_sin_conflicto: bool) -> None:
    expediente = _expediente(sesion, actor, expediente_id, bloquear=True)
    evaluacion = _asegurar_evaluacion(sesion, actor, expediente)
    postores = _postores(sesion, expediente_id)
    if not postores or any(p.informe_consolidado is None for p in postores):
        raise ErrorValidacion("Consolida la evaluación antes de seleccionar.")
    elegido = next((p for p in postores if p.id == seleccionado_id), None)
    if elegido is None:
        raise ErrorValidacion("Elige uno de los posibles proveedores del expediente.")
    if elegido.informe_consolidado["veredicto"] == "no_recomendado":
        raise ErrorValidacion(f"{elegido.razon_social} no es seleccionable: "
                              f"{elegido.informe_consolidado['motivo']}")
    sustento = _texto(sustento, "El sustento de la selección", 3000)
    if len(sustento) < 20:
        raise ErrorValidacion("Explica la selección con más detalle (al menos 20 caracteres).")
    motivos = {}
    for p in postores:
        if p.id == elegido.id:
            continue
        motivo = (descartes.get(p.id) or descartes.get(str(p.id)) or "").strip()
        if not motivo:
            raise ErrorValidacion(f"Explica por qué se descarta a {p.razon_social}.")
        motivos[p.id] = _texto(motivo, "El motivo de descarte", 1000)
    if not declaro_sin_conflicto:
        raise ErrorValidacion(
            "Para enviar la evaluación debes declarar que no tienes conflicto de intereses. "
            "Si lo tienes, abstente: otro especialista de Abastecimiento debe asumirla.")
    ahora = _ahora()
    for p in postores:
        if p.id == elegido.id:
            p.estado, p.motivo_descarte = "seleccionado", None
        else:
            p.estado, p.motivo_descarte = "descartado", motivos[p.id]
    sesion.add(ConflictoInteres(
        expediente_id=expediente_id, revision_previa_id=evaluacion.id, persona_id=actor.persona_id,
        tipo="declaracion_negativa", bloqueante=False, estado="declarado", registrado_en=ahora,
        descripcion=f"{actor.nombre} declara no tener vínculo ni interés con los postores del expediente."))
    # Los vínculos que detectó el análisis quedan registrados para el OCI.
    personas = {pe.dni: pe.id for pe in sesion.scalars(select(Persona))}
    ya = {(c.persona_id, c.proveedor_ruc) for c in sesion.scalars(
        select(ConflictoInteres).where(ConflictoInteres.expediente_id == expediente_id,
                                       ConflictoInteres.tipo == "vinculo_detectado"))}
    for p in postores:
        for h in (p.analisis_dimensiones.get("personas") or {}).get("hallazgos", []):
            vinculo = h.get("vinculo")
            if vinculo and vinculo["dni"] in personas and (personas[vinculo["dni"]], p.ruc) not in ya:
                sesion.add(ConflictoInteres(
                    expediente_id=expediente_id, revision_previa_id=evaluacion.id,
                    persona_id=personas[vinculo["dni"]], proveedor_ruc=p.ruc, tipo="vinculo_detectado",
                    bloqueante=True, estado="en_revision", registrado_en=ahora,
                    descripcion=f"{vinculo['nombre']} ({vinculo['papel']}) figura en {p.razon_social.rstrip('.')}."))
                ya.add((personas[vinculo["dni"]], p.ruc))
    evaluacion.proveedor_seleccionado_ruc = elegido.ruc
    evaluacion.sustento_seleccion = sustento
    evaluacion.estado_revision_independiente = "pendiente"
    evaluacion.comentario_revision_independiente = None
    evaluacion.revisor_independiente_id = None
    evaluacion.enviado_revision_en = ahora
    evaluacion.revisado_independiente_en = None
    expediente.estado_flujo = EN_REVISION
    sesion.flush()
    _registrar(sesion, actor, expediente_id, "evaluacion.enviada",
               f"Selección propuesta: {elegido.razon_social} (S/ {elegido.monto_cotizado:,.2f}). "
               f"Enviada a revisión independiente.", seleccionado_ruc=elegido.ruc,
               descartados=len(motivos))


def revisar_independiente(sesion: Session, actor: Actor, expediente_id: int, *, aprobar: bool,
                          comentario: str) -> None:
    exigir_rol(actor, ROL_ABASTECIMIENTO)
    expediente = _expediente(sesion, actor, expediente_id, bloquear=True)
    evaluacion = _evaluacion(sesion, expediente_id)
    if evaluacion is None or expediente.estado_flujo != EN_REVISION:
        raise ErrorValidacion("Este expediente no tiene una evaluación pendiente de revisión independiente.")
    exigir_otra_persona(actor, evaluacion.evaluador_id,
                        "No puedes hacer la revisión independiente de tu propia evaluación.")
    comentario = _texto(comentario, "El comentario de la revisión", 2000, obligatorio=not aprobar) or ""
    ahora = _ahora()
    evaluacion.revisor_independiente_id = actor.usuario_id
    evaluacion.revisado_independiente_en = ahora
    evaluacion.comentario_revision_independiente = comentario or None
    if aprobar:
        evaluacion.estado_revision_independiente = "aprobada"
        expediente.estado_flujo = APROBADA
        resumen = "Revisión independiente aprobada: la selección queda lista para que el área usuaria confirme la orden."
    else:
        evaluacion.estado_revision_independiente = "observada"
        expediente.estado_flujo = EN_EVALUACION
        for p in _postores(sesion, expediente_id):
            p.estado = "consolidado" if p.informe_consolidado else "analizado"
            p.motivo_descarte = None
        resumen = f"Revisión independiente observada: {comentario}"
    sesion.flush()
    _registrar(sesion, actor, expediente_id,
               "evaluacion.aprobada" if aprobar else "evaluacion.observada", resumen)


# --- Orden sobre la selección aprobada --------------------------------------------------

def confirmar_orden(sesion: Session, actor: Actor, expediente_id: int, *, numero_orden: str,
                    fecha_orden: date, fecha_inicio_prestacion: date | None = None) -> None:
    """El área usuaria registra la orden sobre el proveedor ya aprobado. No elige proveedor."""
    exigir_rol(actor, ROL_AREA_USUARIA)
    expediente = _expediente(sesion, actor, expediente_id, bloquear=True)
    if expediente.estado_flujo != APROBADA:
        raise ErrorValidacion("La orden se registra cuando la selección del proveedor tiene revisión independiente aprobada.")
    evaluacion = _evaluacion(sesion, expediente_id)
    elegido = next((p for p in _postores(sesion, expediente_id)
                    if p.ruc == evaluacion.proveedor_seleccionado_ruc), None)
    numero = _texto(numero_orden, "El número de la orden", 60)
    if fecha_orden < expediente.fecha_requerimiento:
        raise ErrorValidacion("La fecha de la orden no puede ser anterior al requerimiento.")
    if fecha_orden > date.today():
        raise ErrorValidacion("La fecha de la orden no puede ser futura.")
    if fecha_inicio_prestacion and fecha_inicio_prestacion < fecha_orden:
        raise ErrorValidacion("El inicio de la prestación no puede ser anterior a la orden.")
    proveedor = sesion.scalar(select(Proveedor).where(Proveedor.ruc == elegido.ruc))
    if proveedor is None:
        proveedor = Proveedor(ruc=elegido.ruc, razon_social=elegido.razon_social)
        sesion.add(proveedor)
        sesion.flush()
    expediente.proveedor_id = proveedor.id
    expediente.numero_orden = numero
    expediente.fecha_orden = fecha_orden
    expediente.fecha_inicio_prestacion = fecha_inicio_prestacion
    expediente.monto = elegido.monto_cotizado
    expediente.plazo_dias = elegido.plazo_dias
    expediente.estado_flujo = "en_ejecucion"
    sesion.flush()
    bitacora.registrar(
        sesion, actor_id=actor.persona_id, accion="orden.emitida", entidad="expediente",
        entidad_id=expediente.id, expediente_id=expediente.id,
        detalle={"numero_orden": numero, "fecha_orden": fecha_orden, "proveedor_ruc": elegido.ruc,
                 "monto": elegido.monto_cotizado,
                 "resumen": f"Orden {numero} registrada a favor de {elegido.razon_social} "
                            f"por S/ {elegido.monto_cotizado:,.2f}."})
    motor.sincronizar(sesion, [expediente.id])
