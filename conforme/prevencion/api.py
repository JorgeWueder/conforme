"""Revisión precontractual para casos asignados a Abastecimiento."""
import asyncio
from dataclasses import asdict
from datetime import date, datetime, timezone
import json
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from conforme import config, db, repositorio as expedientes
from conforme.dependencias import Sesion, UsuarioActual, actor_actual, usuario_id
from conforme.errores import ErrorValidacion
from conforme.prevencion import demo, evaluacion, investigador, repositorio, simulador
from conforme.prevencion.esquemas import (
    Analizar, Cierre, Compra, Constancia, EditarRevision, Investigar, ResolverHallazgo, VersionEsperada, ruc_valido,
)
from conforme.prevencion.fuentes import CONTROLES

router = APIRouter(prefix="/prevencion", tags=["Prevención"])
Id = Annotated[int, Path(gt=0, lt=2**63)]


def errores(app):
    @app.exception_handler(repositorio.RevisionNoEncontrada)
    async def sin_revision(_request: Request, _error):
        return JSONResponse({"detail": "La revisión no existe o está fuera de tu alcance."}, status_code=404)

    @app.exception_handler(repositorio.VersionSuperada)
    async def version_superada(_request: Request, _error):
        return JSONResponse({"detail": "La revisión cambió. Actualízala para continuar."}, status_code=409)


def _demo_disponible():
    return config.leer("PREVENCION_DEMO") == "1"


def _validar_compra(compra):
    if not all(ruc_valido(ruc) for ruc in [compra.entidad_ruc, *(c.ruc for c in compra.candidatos)]):
        raise ErrorValidacion("Revisa los RUC de la entidad y de los candidatos, incluido su dígito verificador.")
    if compra.fecha > date.today():
        raise ErrorValidacion("La fecha de evaluación debe ser hoy o anterior.")


def _controles(compra):
    controles = []
    for clave, control in CONTROLES.items():
        sujetos = compra["candidatos"] if control.por_candidato else [{"ruc": None}]
        for sujeto in sujetos:
            ruc = sujeto["ruc"]
            controles.append(dict(
                id=f"{clave}:{ruc}" if ruc else clave, ruc=ruc, **asdict(control),
            ))
    return controles


def _detalle(revision):
    return {"analisis": {}, **revision, "controles": _controles(revision["compra"])}


def _pausa_analisis_segundos() -> float:
    crudo = config.leer("PREVENCION_PAUSA_MS", "240")
    try:
        return max(0.0, min(2.0, int(crudo) / 1000.0))
    except (TypeError, ValueError):
        return 0.24


def _linea_ndjson(evento: dict) -> str:
    return json.dumps(evento, ensure_ascii=False, default=str) + "\n"


@router.get("")
def listar(sesion: Sesion, actor: UsuarioActual,
           antes_de: Annotated[int | None, Query(gt=0, lt=2**63)] = None):
    filas = repositorio.listar(sesion, actor, antes_de)
    return dict(revisiones=filas[:30], siguiente=filas[29]["id"] if len(filas) > 30 else None,
                demo_disponible=_demo_disponible())


@router.post("", status_code=201)
def crear(compra: Compra, sesion: Sesion, actor: UsuarioActual):
    _validar_compra(compra)
    return _detalle(repositorio.crear(sesion, actor, compra))


@router.post("/demo", status_code=201)
def crear_demo(sesion: Sesion, actor: UsuarioActual):
    if not _demo_disponible():
        raise HTTPException(404, "El caso de ejemplo está desactivado.")
    return _detalle(repositorio.crear(sesion, actor, demo.compra_demo(), demo=True))


@router.get("/{revision_id}")
def obtener(revision_id: Id, sesion: Sesion, actor: UsuarioActual):
    return _detalle(repositorio.obtener(sesion, actor, revision_id))


@router.put("/{revision_id}")
def editar(revision_id: Id, datos: EditarRevision, sesion: Sesion, actor: UsuarioActual):
    anterior = repositorio.base_de_cambio(sesion, actor, revision_id, datos.version)
    if anterior["demo"]:
        raise ErrorValidacion("El caso de ejemplo tiene datos fijos.")
    _validar_compra(datos.compra)
    base = repositorio.base(datos.compra, demo=False)
    if base["compra"] == anterior["compra"]:
        return _detalle(repositorio.obtener(sesion, actor, revision_id))
    return _detalle(repositorio.guardar(sesion, actor, revision_id, datos.version, base, "editada"))


@router.post("/{revision_id}/evaluacion")
def evaluar(revision_id: Id, datos: VersionEsperada, sesion: Sesion, actor: UsuarioActual):
    base = repositorio.base_de_cambio(sesion, actor, revision_id, datos.version)
    fuentes, hallazgos = (demo.resultados(base["compra"]) if base["demo"]
                          else evaluacion.cruzar(sesion, base["compra"]))
    anteriores = {h["id"]: h for h in base["hallazgos"]}
    base["resoluciones"] = {h["id"]: base["resoluciones"][h["id"]] for h in hallazgos
                            if h["id"] in base["resoluciones"] and h == anteriores.get(h["id"])}
    base.update(fuentes=fuentes, hallazgos=hallazgos)
    return _detalle(repositorio.guardar(sesion, actor, revision_id, datos.version, base, "evaluada"))


@router.post("/{revision_id}/analizar")
async def analizar(revision_id: Id, datos: Analizar, identificador: Annotated[int | None, Depends(usuario_id)]):
    # Valida acceso, versión y alcance antes de abrir el flujo en tiempo real sin retener conexión DB.
    with db.sesion() as sesion:
        actor = actor_actual(sesion, identificador)
        base = repositorio.base_de_cambio(sesion, actor, revision_id, datos.version, bloquear=False)
    candidatos_rucs = {c["ruc"] for c in base["compra"]["candidatos"]}
    if datos.ruc is not None and datos.ruc not in candidatos_rucs:
        raise ErrorValidacion("Selecciona un proveedor registrado en esta compra.")

    plan = simulador.plan_analisis(base["compra"], es_demo=base["demo"], ruc=datos.ruc)
    pausa = _pausa_analisis_segundos()

    async def flujo():
        yield _linea_ndjson(dict(
            tipo="inicio",
            alcance=datos.ruc or "todos",
            total_pasos=plan["total_pasos"],
            proveedores=[dict(ruc=p["ruc"], nombre=p["nombre"]) for p in plan["proveedores"]],
            simulado=True,
        ))
        paso_actual = 0
        registro_analisis: dict[str, dict] = {}
        momento = datetime.now(timezone.utc).isoformat()

        for indice, proveedor in enumerate(plan["proveedores"], 1):
            yield _linea_ndjson(dict(
                tipo="proveedor_inicio",
                ruc=proveedor["ruc"],
                nombre=proveedor["nombre"],
                indice=indice,
                total=len(plan["proveedores"]),
            ))
            verificaciones = []
            for paso in proveedor["pasos"]:
                yield _linea_ndjson(dict(
                    tipo="paso",
                    ruc=proveedor["ruc"],
                    nombre=proveedor["nombre"],
                    fuente_id=paso["fuente_id"],
                    fuente=paso["fuente"],
                    frente=paso["frente"],
                    mensaje=paso["consulta"],
                    progreso=paso_actual,
                    total_pasos=plan["total_pasos"],
                ))
                if pausa:
                    await asyncio.sleep(pausa)
                paso_actual += 1
                verificacion = dict(
                    fuente_id=paso["fuente_id"],
                    fuente=paso["fuente"],
                    frente=paso["frente"],
                    estado=paso["estado"],
                    mensaje=paso["mensaje"],
                )
                verificaciones.append(verificacion)
                yield _linea_ndjson(dict(
                    tipo="paso_resultado",
                    ruc=proveedor["ruc"],
                    nombre=proveedor["nombre"],
                    **verificacion,
                    hallazgo=paso["hallazgo"],
                    progreso=paso_actual,
                    total_pasos=plan["total_pasos"],
                ))
            resumen_prov = dict(
                estado="analizado",
                nivel=proveedor["nivel"],
                resumen=proveedor["resumen"],
                hallazgos=len(proveedor["hallazgos"]),
                actualizado_en=momento,
                simulado=True,
                verificaciones=verificaciones,
            )
            registro_analisis[proveedor["ruc"]] = resumen_prov
            yield _linea_ndjson(dict(
                tipo="proveedor_fin",
                ruc=proveedor["ruc"],
                nombre=proveedor["nombre"],
                nivel=proveedor["nivel"],
                resumen=proveedor["resumen"],
                hallazgos=len(proveedor["hallazgos"]),
                verificaciones=verificaciones,
            ))

        if plan["pasos_compra"]:
            yield _linea_ndjson(dict(
                tipo="compra_inicio",
                mensaje="Verificando alcance general de la compra y cotizaciones…",
            ))
            verificaciones_compra = []
            for paso in plan["pasos_compra"]:
                yield _linea_ndjson(dict(
                    tipo="paso",
                    ruc=None,
                    nombre="Alcance de la compra",
                    fuente_id=paso["fuente_id"],
                    fuente=paso["fuente"],
                    frente=paso["frente"],
                    mensaje=paso["consulta"],
                    progreso=paso_actual,
                    total_pasos=plan["total_pasos"],
                ))
                if pausa:
                    await asyncio.sleep(pausa)
                paso_actual += 1
                verificacion = dict(
                    fuente_id=paso["fuente_id"],
                    fuente=paso["fuente"],
                    frente=paso["frente"],
                    estado=paso["estado"],
                    mensaje=paso["mensaje"],
                )
                verificaciones_compra.append(verificacion)
                yield _linea_ndjson(dict(
                    tipo="paso_resultado",
                    ruc=None,
                    nombre="Alcance de la compra",
                    **verificacion,
                    hallazgo=paso["hallazgo"],
                    progreso=paso_actual,
                    total_pasos=plan["total_pasos"],
                ))
            registro_analisis["__compra__"] = dict(
                estado="analizado",
                nivel=simulador._nivel_proveedor(plan["hallazgos_compra"]),
                resumen=simulador._resumen_proveedor(plan["hallazgos_compra"]),
                hallazgos=len(plan["hallazgos_compra"]),
                actualizado_en=momento,
                simulado=True,
                verificaciones=verificaciones_compra,
            )

        try:
            with db.sesion() as sesion:
                actor = actor_actual(sesion, identificador)
                actual = repositorio.base_de_cambio(sesion, actor, revision_id, datos.version)
                anteriores = {h["id"]: h for h in actual["hallazgos"]}
                if datos.ruc is None:
                    nuevos_hallazgos = [
                        *(h for p in plan["proveedores"] for h in p["hallazgos"]),
                        *plan["hallazgos_compra"],
                    ]
                else:
                    conservados = [h for h in actual["hallazgos"] if h["ruc"] != datos.ruc]
                    nuevos_hallazgos = conservados + [h for p in plan["proveedores"] for h in p["hallazgos"]]

                actual["resoluciones"] = {
                    h["id"]: actual["resoluciones"][h["id"]]
                    for h in nuevos_hallazgos
                    if h["id"] in actual["resoluciones"] and h == anteriores.get(h["id"])
                }
                analisis_previo = dict(actual.get("analisis") or {})
                analisis_previo.update(registro_analisis)
                actual.update(
                    fuentes=plan["fuentes"],
                    hallazgos=nuevos_hallazgos,
                    analisis=analisis_previo,
                )
                guardada = _detalle(repositorio.guardar(sesion, actor, revision_id, datos.version, actual, "analizada"))
        except repositorio.VersionSuperada:
            yield _linea_ndjson(dict(
                tipo="error",
                detail="La revisión cambió mientras se ejecutaba el análisis. Recarga la ficha para continuar.",
            ))
            return
        except ErrorValidacion as error:
            yield _linea_ndjson(dict(tipo="error", detail=str(error)))
            return

        yield _linea_ndjson(dict(tipo="completado", revision=guardada))

    return StreamingResponse(
        flujo(),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache, no-store"},
    )


@router.post("/{revision_id}/constancias")
def constancia(revision_id: Id, datos: Constancia, sesion: Sesion, actor: UsuarioActual):
    base = repositorio.base_de_cambio(sesion, actor, revision_id, datos.version)
    if datos.control not in {c["id"] for c in _controles(base["compra"])}:
        raise ErrorValidacion("Selecciona una comprobación de esta revisión.")
    if datos.fecha_hecho and datos.fecha_hecho > date.today():
        raise ErrorValidacion("La fecha de la comprobación debe ser hoy o anterior.")
    base["constancias"][datos.control] = datos.model_dump(mode="json", exclude={"control", "version"})
    return _detalle(repositorio.guardar(sesion, actor, revision_id, datos.version, base, "constancia"))


@router.post("/{revision_id}/hallazgos")
def resolver(revision_id: Id, datos: ResolverHallazgo, sesion: Sesion, actor: UsuarioActual):
    base = repositorio.base_de_cambio(sesion, actor, revision_id, datos.version)
    if datos.hallazgo not in {h["id"] for h in base["hallazgos"]}:
        raise ErrorValidacion("Selecciona un hallazgo de esta revisión.")
    base["resoluciones"][datos.hallazgo] = datos.model_dump(mode="json", exclude={"hallazgo", "version"})
    return _detalle(repositorio.guardar(sesion, actor, revision_id, datos.version, base, "hallazgo_revisado"))


@router.post("/{revision_id}/investigaciones")
def investigar(revision_id: Id, datos: Investigar, identificador: Annotated[int | None, Depends(usuario_id)]):
    # No ocupar una conexión de la base mientras se leen fuentes y eve ejecuta su turno.
    with db.sesion() as sesion:
        actor = actor_actual(sesion, identificador)
        base = repositorio.base_de_cambio(sesion, actor, revision_id, datos.version, bloquear=False)
    if datos.ruc not in {c["ruc"] for c in base["compra"]["candidatos"]}:
        raise ErrorValidacion("Selecciona un candidato de esta compra.")
    hallazgos_cand = [h for h in base["hallazgos"] if h["ruc"] == datos.ruc]
    evidencias = [e for h in hallazgos_cand for e in h["evidencias"]]
    actos = {e.get("acto") for e in evidencias if e.get("acto")}
    acto = datos.acto if datos.acto in actos else None
    if datos.acto and not acto:
        raise ErrorValidacion("Selecciona un número de acto que figure en la ficha del candidato.")
    if not acto and len(actos) == 1:
        acto = next(iter(actos))
    urls = [e["url_acto"] for e in evidencias if e.get("url_acto") and (not acto or e.get("acto") == acto)]
    es_simulado = any(h.get("simulado") for h in hallazgos_cand) or bool((base.get("analisis") or {}).get(datos.ruc, {}).get("simulado"))
    nombre_cand = next((c["nombre"] for c in base["compra"]["candidatos"] if c["ruc"] == datos.ruc), None)
    try:
        resultado = investigador.investigar(
            datos.ruc, acto, base["compra"]["fecha"], urls,
            sintetico=base["demo"], simulado=es_simulado, nombre=nombre_cand, operacion=uuid4().hex,
        )
    except investigador.InvestigadorNoDisponible as error:
        raise HTTPException(503, "El investigador documental está temporalmente fuera de servicio.") from error

    with db.sesion() as sesion:
        actor = actor_actual(sesion, identificador)
        base = repositorio.base_de_cambio(sesion, actor, revision_id, datos.version)
        base["investigaciones"] = [i for i in base["investigaciones"] if (i["ruc"], i["acto"]) != (datos.ruc, acto)]
        base["investigaciones"].append(dict(ruc=datos.ruc, acto=acto, **resultado))
        return _detalle(repositorio.guardar(sesion, actor, revision_id, datos.version, base, "investigada"))


@router.post("/{revision_id}/cierre")
def cerrar(revision_id: Id, datos: Cierre, sesion: Sesion, actor: UsuarioActual):
    base = repositorio.base_de_cambio(sesion, actor, revision_id, datos.version)
    if not base["fuentes"]:
        raise ErrorValidacion("Consulta las fuentes antes de cerrar la revisión.")
    if any(base["constancias"].get(c["id"], {}).get("resultado") in (None, "pendiente")
           for c in _controles(base["compra"]) if c["obligatorio"]):
        raise ErrorValidacion("Registra el resultado de todas las comprobaciones obligatorias.")
    if any(base["resoluciones"].get(h["id"], {}).get("resultado") in (None, "pendiente")
           for h in base["hallazgos"] if h["prioridad"] == "verificar"):
        raise ErrorValidacion("Registra una actuación para los hallazgos que requieren verificación.")
    if datos.expediente_id and not expedientes.obtener_expediente(sesion, actor, datos.expediente_id):
        raise ErrorValidacion("El expediente vinculado no existe o está fuera de tu alcance.")
    base.update(estado="cerrada", cierre=datos.model_dump(mode="json", exclude={"version"}))
    return _detalle(repositorio.guardar(sesion, actor, revision_id, datos.version, base, "cerrada"))
