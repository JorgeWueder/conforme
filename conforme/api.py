"""API HTTP de Conforme. Las operaciones de dominio pasan por el repositorio."""
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from urllib.parse import quote, urlsplit

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from conforme import (
    auth, bitacora, db, entregables, evidencias, integridad, normativa, reporte, repositorio, sello,
)
from conforme.dependencias import (
    COOKIE, DURACION_SESION, FIRMADOR, Sesion, UsuarioActual, actor_actual, usuario_id,
)
from conforme.errores import ErrorValidacion
from conforme.ia import extractor
from conforme.ia import evidencias as revision_evidencias
from conforme.modelos import ROL_ABASTECIMIENTO, ROL_AREA_USUARIA
from conforme.permisos import Actor, exigir_rol
from conforme.proveedores import repositorio as evaluacion_proveedores

router = APIRouter()


@router.get("/salud")
def salud():
    """Comprobación de salud del despliegue. No toca la base para no despertar Neon."""
    return {"estado": "ok"}


class Credenciales(BaseModel):
    username: str
    password: str


@router.post("/sesion")
def ingresar(datos: Credenciales, request: Request, response: Response, sesion: Sesion):
    actor = auth.autenticar(sesion, datos.username, datos.password)
    if actor is None:
        raise HTTPException(401, "Usuario o contraseña incorrectos.")
    response.set_cookie(COOKIE, FIRMADOR.dumps(actor.usuario_id), max_age=DURACION_SESION,
                        httponly=True, samesite="lax", secure=request.url.scheme == "https")
    return actor


@router.get("/sesion")
def sesion_actual(actor: UsuarioActual):
    return actor


@router.delete("/sesion", status_code=204)
def salir(request: Request):
    respuesta = Response(status_code=204)
    respuesta.delete_cookie(COOKIE, httponly=True, samesite="lax",
                            secure=request.url.scheme == "https")
    return respuesta


def expediente_visible(sesion: Session, actor: Actor, expediente_id: int) -> dict:
    expediente = repositorio.obtener_expediente(sesion, actor, expediente_id)
    if expediente is None:
        raise HTTPException(404, "El expediente no existe o está fuera de tu alcance.")
    return expediente


def leer_archivo(archivo: UploadFile, limite: int) -> bytes:
    contenido = archivo.file.read(limite + 1)
    if len(contenido) > limite:
        raise ErrorValidacion(f"El archivo «{archivo.filename}» supera los {limite // (1024 * 1024)} MB.")
    return contenido


def adjunto(contenido: bytes, mime: str, nombre: str | None = None) -> Response:
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(nombre, safe='')}"} if nombre else {}
    return Response(contenido, media_type=mime, headers=headers)


@router.get("/expedientes")
def listar_expedientes(sesion: Sesion, actor: UsuarioActual, texto: str = ""):
    return repositorio.listar_expedientes(sesion, actor, texto=texto)


@router.get("/proveedores")
def listar_proveedores(sesion: Sesion, actor: UsuarioActual):
    exigir_rol(actor, ROL_AREA_USUARIA)
    return repositorio.listar_proveedores(sesion, actor)


@router.post("/entregables/csv")
def previsualizar_csv(actor: UsuarioActual, archivo: UploadFile):
    exigir_rol(actor, ROL_AREA_USUARIA)
    filas, errores = entregables.leer_csv(leer_archivo(archivo, evidencias.TAMANO_MAXIMO))
    return {"entregables": filas, "errores": errores}


class NuevoEntregable(BaseModel):
    numero: int | str
    descripcion: str


class PostorReferencial(BaseModel):
    ruc: str = Field(max_length=11)
    razon_social: str = Field(max_length=200)
    monto_cotizado: Decimal
    plazo_dias: int
    contacto_correo: str | None = Field(default=None, max_length=120)
    contacto_telefono: str | None = Field(default=None, max_length=40)
    proforma_ref: str | None = Field(default=None, max_length=120)


class NuevoRequerimiento(BaseModel):
    """El área usuaria registra lo que necesita. No elige al proveedor ni registra la orden:
    Abastecimiento evalúa a los posibles proveedores y la orden se confirma después."""
    tipo: Literal["bien", "servicio"]
    descripcion: str = Field(max_length=2000)
    proyecto_referencia: str | None = None
    conformidad_plazo_especial: bool = False
    fecha_requerimiento: date
    plazo_dias: int
    monto: Decimal
    entregables: list[NuevoEntregable]
    origen_entregables: Literal["manual", "csv", "tdr"] = "manual"
    postores: list[PostorReferencial] = Field(default=[], max_length=8)


@router.post("/expedientes", status_code=201)
def crear_requerimiento(datos: NuevoRequerimiento, sesion: Sesion, actor: UsuarioActual):
    return {"id": repositorio.crear_requerimiento(sesion, actor, **datos.model_dump())}


def _origen_publico(request: Request) -> str:
    # Next.js reescribe Host hacia FastAPI y conserva el host público en este encabezado.
    host = request.headers.get("x-forwarded-host", "")
    if host and host.isascii() and not any(c.isspace() or c in "/\\@?#," for c in host):
        try:
            origen = urlsplit(f"{request.url.scheme}://{host}")
            if origen.hostname and origen.port != 0:
                return f"{origen.scheme}://{origen.netloc}"
        except ValueError:
            pass
    return str(request.base_url).rstrip("/")


@router.get("/expedientes/{expediente_id}")
def detalle_expediente(expediente_id: int, request: Request, sesion: Sesion, actor: UsuarioActual):
    expediente = expediente_visible(sesion, actor, expediente_id)
    conformidad = repositorio.obtener_conformidad(sesion, actor, expediente_id)
    if conformidad and conformidad["codigo_sello"]:
        origen = _origen_publico(request)
        conformidad["url_sello"] = sello.url_verificacion(conformidad["codigo_sello"], sello.url_base(origen))
        conformidad["aviso_url"] = sello.aviso_url_base(origen)
    return {
        "expediente": expediente,
        "fecha_limite": normativa.fecha_limite(expediente["fecha_orden"], expediente["plazo_dias"],
                                              expediente["fecha_inicio_prestacion"])
        if expediente["fecha_orden"] else None,
        "seleccion": evaluacion_proveedores.seleccion(sesion, actor, expediente_id),
        "plazo_maximo_conformidad": normativa.plazo_conformidad(expediente["conformidad_plazo_especial"]),
        "conformidad": conformidad,
        "historial_conformidades": repositorio.historial_conformidades(sesion, actor, expediente_id),
        "entregables": repositorio.listar_entregables(sesion, actor, expediente_id),
        "alertas": repositorio.listar_alertas(sesion, actor, expediente_id=expediente_id),
        "reglas": normativa.NOMBRE_REGLA,
        "pagos": repositorio.listar_pagos(sesion, actor, expediente_id),
        "eventos": repositorio.linea_de_tiempo(sesion, actor, expediente_id),
    }


@router.get("/indicadores")
def indicadores(sesion: Sesion, actor: UsuarioActual):
    return repositorio.indicadores(sesion, actor)


@router.get("/dashboard")
def panel_dashboard(sesion: Sesion, actor: UsuarioActual):
    from conforme import dashboard
    return dashboard.resumen(sesion, actor)


@router.get("/expedientes/{expediente_id}/reporte")
def reporte_expediente(expediente_id: int, request: Request, sesion: Sesion, actor: UsuarioActual):
    datos = detalle_expediente(expediente_id, request, sesion, actor)
    cadena = bitacora.verificar_cadena_cacheada(sesion)
    pdf = reporte.generar_pdf(datos, actor=f"{actor.nombre} ({actor.username})",
                              cadena_integra=cadena.resultado.integra, registros=cadena.resultado.total)
    codigo = datos["expediente"]["codigo"]
    return adjunto(pdf, "application/pdf", f"reporte-trazabilidad-{codigo}.pdf")


@router.get("/expedientes/{expediente_id}/penalidad")
def calcular_penalidad(expediente_id: int, entrega: date, sesion: Sesion, actor: UsuarioActual):
    """Orientación para el formulario: la misma cuenta que usa la regla R2."""
    expediente = expediente_visible(sesion, actor, expediente_id)
    if expediente["fecha_orden"] is None:
        raise ErrorValidacion("El expediente aún no tiene orden registrada.")
    monto, plazo = Decimal(expediente["monto"]), expediente["plazo_dias"]
    limite = normativa.fecha_limite(expediente["fecha_orden"], plazo, expediente["fecha_inicio_prestacion"])
    atraso = max(0, (entrega - limite).days)
    return {
        "fecha_limite": limite,
        "dias_atraso": atraso,
        "penalidad_esperada": str(normativa.penalidad_esperada(monto, plazo, atraso)),
        "penalidad_tope": str(normativa.penalidad_tope(monto)),
        "tolerancia": str(normativa.PENALIDAD_TOLERANCIA),
        "plazo_maximo_conformidad": normativa.plazo_conformidad(expediente["conformidad_plazo_especial"]),
    }


@router.get("/expedientes/{expediente_id}/sello")
def imagen_sello(expediente_id: int, request: Request, sesion: Sesion, actor: UsuarioActual,
                 descarga: bool = False):
    expediente = expediente_visible(sesion, actor, expediente_id)
    conformidad = repositorio.obtener_conformidad(sesion, actor, expediente_id)
    if not conformidad or not conformidad["codigo_sello"]:
        raise HTTPException(404, "El expediente no tiene sello.")
    base = sello.url_base(_origen_publico(request))
    codigo = conformidad["codigo_sello"]
    if descarga:
        return adjunto(sello.png_sello(codigo, expediente["codigo"], conformidad["sello_hash"], base),
                       "image/png", f"sello-{expediente['codigo']}.png")
    return adjunto(sello.png_qr(codigo, base), "image/png")


@router.get("/evidencias/{evidencia_id}")
def ver_evidencia(evidencia_id: int, sesion: Sesion, actor: UsuarioActual, descarga: bool = False):
    archivo = repositorio.obtener_evidencia(sesion, actor, evidencia_id)
    if not archivo:
        raise HTTPException(404, "Evidencia no encontrada.")
    mostrar = archivo["mime"] in ("image/jpeg", "image/png") and not descarga
    return adjunto(bytes(archivo["contenido"]), archivo["mime"],
                   None if mostrar else archivo["nombre_archivo"])


class ItemConformidad(BaseModel):
    entregable_id: int
    cumplido: bool
    observacion: str = ""
    cantidad_archivos: int = Field(default=0, ge=0)


class Conformidad(BaseModel):
    fecha_conformidad: date
    fecha_entrega_real: date | None = None
    penalidad_aplicada: Decimal
    sustento_penalidad: str = Field(default="", max_length=2000)
    tipo_sustento_penalidad: Literal["ampliacion", "no_imputable"] | None = None
    referencia_sustento_penalidad: str = Field(default="", max_length=120)
    observaciones: str = ""
    items: list[ItemConformidad]


class CriterioEvidencia(BaseModel):
    entregable_id: int
    criterio_evidencia: str = Field(max_length=300)


@router.post("/expedientes/{expediente_id}/criterios-evidencia", status_code=204)
def guardar_criterios_evidencia(expediente_id: int, criterios: list[CriterioEvidencia],
                               sesion: Sesion, actor: UsuarioActual):
    repositorio.definir_criterios_evidencia(
        sesion, actor, expediente_id, [c.model_dump() for c in criterios])


class ObservacionEntrega(BaseModel):
    entregable_id: int
    texto: str = Field(max_length=1000)


@router.post("/expedientes/{expediente_id}/observaciones-entrega", status_code=204)
def registrar_observacion_de_entrega(
    expediente_id: int, datos: ObservacionEntrega, sesion: Sesion, actor: UsuarioActual,
):
    repositorio.registrar_observacion_de_entrega(sesion, actor, expediente_id, **datos.model_dump())
    return Response(status_code=204)


class ComunicacionObservacion(BaseModel):
    entregable_id: int
    plazo_dias: int
    canal: str = Field(max_length=120)
    referencia: str = Field(default="", max_length=120)


@router.post("/expedientes/{expediente_id}/comunicaciones", status_code=204)
def comunicar_observacion(
    expediente_id: int, datos: ComunicacionObservacion, sesion: Sesion, actor: UsuarioActual,
):
    repositorio.comunicar_observacion(sesion, actor, expediente_id, **datos.model_dump())
    return Response(status_code=204)


class RevisionConformidad(BaseModel):
    favorable: bool
    motivo: str = Field(max_length=1000)
    referencia_derivacion: str = Field(default="", max_length=120)
    advertencias_revisadas: bool = False


@router.post("/expedientes/{expediente_id}/revision", status_code=204)
def revisar_conformidad(
    expediente_id: int, datos: RevisionConformidad, sesion: Sesion, actor: UsuarioActual,
):
    repositorio.revisar_conformidad(sesion, actor, expediente_id, **datos.model_dump())
    return Response(status_code=204)


@router.post("/expedientes/{expediente_id}/conformidad", status_code=201)
def registrar_conformidad(expediente_id: int, datos: Annotated[str, Form()],
                          identificador: Annotated[int | None, Depends(usuario_id)],
                          archivos: Annotated[list[UploadFile] | None, File()] = None):
    # La lectura del modelo ocurre fuera de la transacción de PostgreSQL.
    with db.sesion() as sesion:
        actor = actor_actual(sesion, identificador)
        exigir_rol(actor, ROL_AREA_USUARIA)
        expediente = expediente_visible(sesion, actor, expediente_id)
        lecturas = repositorio.listar_extracciones(sesion, actor, expediente_id)
        aprobada = next((l for l in lecturas if l["estado"] == "aprobada" and
                         l["origen"] == "modelo"), None)
        contexto = {"codigo": expediente["codigo"], "descripcion": expediente["descripcion"],
                    "entregables": repositorio.listar_entregables(sesion, actor, expediente_id),
                    "tdr": aprobada["resultado"] if aprobada else None}
    try:
        formulario = Conformidad.model_validate_json(datos)
    except ValidationError as error:
        raise ErrorValidacion("Revisa los datos de la conformidad.") from error
    archivos = archivos or []
    if sum(item.cantidad_archivos for item in formulario.items) != len(archivos):
        raise ErrorValidacion("La cantidad de evidencias no coincide con los entregables.")
    restantes = iter(archivos)
    items = []
    for item in formulario.items:
        evidencia_item = []
        for _ in range(item.cantidad_archivos):
            archivo = next(restantes)
            evidencia_item.append(evidencias.preparar(
                archivo.filename or "evidencia", archivo.content_type,
                leer_archivo(archivo, evidencias.TAMANO_MAXIMO)))
        items.append({**item.model_dump(exclude={"cantidad_archivos"}), "evidencias": evidencia_item})
    verificacion = revision_evidencias.verificar(contexto, items)
    with db.sesion() as sesion:
        actor = actor_actual(sesion, identificador)
        identificador_conformidad = repositorio.registrar_conformidad(
            sesion, actor, expediente_id, **formulario.model_dump(exclude={"items"}),
            items=items, verificacion_ia=verificacion,
        )
        alertas = repositorio.listar_alertas(sesion, actor, expediente_id=expediente_id)
        cantidad_alertas = sum(alerta["vigente"] for alerta in alertas)
    return {"id": identificador_conformidad, "alertas": cantidad_alertas,
            "advertencias_evidencia": len(verificacion["hallazgos"])}


class Pago(BaseModel):
    fecha_pago: date
    monto: Decimal
    penalidad_descontada: Decimal
    referencia_siaf: str | None = None


@router.post("/expedientes/{expediente_id}/pagos", status_code=201)
def registrar_pago(expediente_id: int, datos: Pago, sesion: Sesion, actor: UsuarioActual):
    return {"id": repositorio.registrar_pago(sesion, actor, expediente_id, **datos.model_dump())}


@router.get("/expedientes/{expediente_id}/verificacion-pago")
def verificacion_pago(expediente_id: int, sesion: Sesion, actor: UsuarioActual):
    return repositorio.verificar_pago(sesion, actor, expediente_id)


@router.get("/pagos/bandeja")
def bandeja_pagos(sesion: Sesion, actor: UsuarioActual):
    return repositorio.bandeja_pagos(sesion, actor)


@router.get("/adaptadores")
def estado_adaptadores(actor: UsuarioActual):
    from conforme.adaptadores import estado_adaptadores as obtener_estado
    return obtener_estado()


@router.post("/expedientes/{expediente_id}/reevaluar")
def reevaluar(expediente_id: int, sesion: Sesion, actor: UsuarioActual):
    return {"nuevas": repositorio.reevaluar(sesion, actor, expediente_id)}


@router.get("/alertas")
def listar_alertas(sesion: Sesion, actor: UsuarioActual):
    return {"alertas": repositorio.listar_alertas(sesion, actor),
            "reglas": {**normativa.NOMBRE_REGLA, "OCI": "Seguimiento de Auditoría"}}


@router.get("/integridad")
def panel_integridad(sesion: Sesion, actor: UsuarioActual):
    return integridad.panel(sesion, actor)


class ActuacionOCI(BaseModel):
    entidad: Literal["expediente", "revision_previa", "conflicto_interes"]
    entidad_id: int = Field(gt=0)
    tipo: Literal[
        "recomendar_abstencion", "derivar_sancion", "solicitar_descargos", "archivar_sustento",
        "observacion_seguimiento", "requerimiento_info", "recomendacion", "alerta_seguimiento",
    ]
    descripcion: str = Field(min_length=15, max_length=2000)


@router.post("/integridad/actuaciones", status_code=201)
def registrar_actuacion_oci(datos: ActuacionOCI, sesion: Sesion, actor: UsuarioActual):
    return {"id": integridad.registrar_actuacion(sesion, actor, **datos.model_dump())}


@router.get("/alertas/{alerta_id}/revisiones")
def revisiones(alerta_id: int, sesion: Sesion, actor: UsuarioActual):
    return repositorio.revisiones_de_alerta(sesion, actor, alerta_id)


class Revision(BaseModel):
    accion: Literal["descargo", "cierre", "escalamiento"]
    texto: str


@router.post("/alertas/{alerta_id}/revisiones", status_code=204)
def revisar_alerta(alerta_id: int, datos: Revision, sesion: Sesion, actor: UsuarioActual):
    acciones = {"descargo": repositorio.registrar_descargo, "cierre": repositorio.cerrar_alerta,
                "escalamiento": repositorio.escalar_alerta}
    acciones[datos.accion](sesion, actor, alerta_id, datos.texto)


@router.get("/bitacora")
def listar_bitacora(sesion: Sesion, actor: UsuarioActual):
    return repositorio.listar_bitacora(sesion, actor, limite=200)


@router.get("/bitacora/integridad")
def verificar_integridad(sesion: Sesion, actor: UsuarioActual):
    return repositorio.verificar_integridad(sesion, actor)


@router.get("/sellos/{codigo}")
def verificar_sello(codigo: str, sesion: Sesion, forzar: bool = False):
    resultado = repositorio.consultar_sello(sesion, codigo.strip(), forzar=forzar)
    if resultado is None:
        raise HTTPException(404, "No se encontró ninguna conformidad con ese código. Revisa que esté completo.")
    return reducir_sello_publico(resultado)


def reducir_sello_publico(resultado: dict) -> dict:
    """La verificación sin sesión solo dice si el rastro está íntegro y qué cubre.

    No expone personas, proveedor, importes, notas, descripciones ni miniaturas: eso se
    consulta dentro de la sesión, con el alcance de cada rol."""
    for campo in ("monto", "penalidad_aplicada", "conformante", "conformante_cargo",
                  "proveedor", "observaciones", "descripcion"):
        resultado[campo] = None
    entregables = []
    for entregable in resultado["entregables"]:
        entregables.append({
            "numero": entregable["numero"], "cumplido": entregable["cumplido"],
            "descripcion": f"Entregable {entregable['numero']}", "observacion": "",
            "evidencias": [
                {"nombre_archivo": f"Evidencia {i}", "mime": "", "sha256": evidencia["sha256"],
                 "coincide": evidencia["coincide"], "miniatura": None}
                for i, evidencia in enumerate(entregable["evidencias"], start=1)
            ],
        })
    resultado["entregables"] = entregables
    resultado["reducido"] = True
    return resultado


@router.get("/ia/ejemplo")
def ejemplo_ia(actor: UsuarioActual):
    exigir_rol(actor, ROL_AREA_USUARIA)
    if not extractor.PDF_EJEMPLO.is_file():
        raise HTTPException(404, "El PDF de ejemplo no está disponible.")
    return FileResponse(extractor.PDF_EJEMPLO, filename="terminos_referencia_ejemplo.pdf",
                        media_type="application/pdf")


@router.get("/expedientes/{expediente_id}/lecturas")
def listar_lecturas(expediente_id: int, sesion: Sesion, actor: UsuarioActual):
    exigir_rol(actor, ROL_AREA_USUARIA, ROL_ABASTECIMIENTO)
    expediente = expediente_visible(sesion, actor, expediente_id)
    existentes = repositorio.listar_entregables(sesion, actor, expediente_id)
    lecturas = repositorio.listar_extracciones(sesion, actor, expediente_id)
    pendiente = next((lectura for lectura in lecturas if lectura["estado"] == "propuesta"), None)
    if pendiente:
        pendiente["avisos_coherencia"] = extractor.avisos_de_coherencia(
            extractor.PropuestaIA.model_validate(pendiente["resultado"]), expediente,
            pendiente["origen"], [item["descripcion"] for item in existentes],
        )
    return {"expediente": expediente, "entregables": existentes, "lecturas": lecturas,
            "observaciones": repositorio.listar_observaciones_tdr(sesion, actor, expediente_id),
            "tdr": repositorio.estado_tdr(sesion, actor, expediente_id),
            "hay_ejemplo": extractor.PDF_EJEMPLO.is_file()}


class ObservacionTdr(BaseModel):
    detalle: str = Field(max_length=2000)
    severidad: Literal["bloqueante", "advertencia"] = "bloqueante"


@router.post("/expedientes/{expediente_id}/tdr/observaciones", status_code=204)
def observar_tdr(expediente_id: int, datos: ObservacionTdr, sesion: Sesion, actor: UsuarioActual):
    repositorio.registrar_observacion_tdr(sesion, actor, expediente_id, **datos.model_dump())


class RespuestaTdr(BaseModel):
    estado: Literal["corregida", "justificada"]
    respuesta: str = Field(max_length=2000)


@router.post("/expedientes/{expediente_id}/tdr/observaciones/{observacion_id}/responder",
             status_code=204)
def responder_tdr(expediente_id: int, observacion_id: int, datos: RespuestaTdr,
                  sesion: Sesion, actor: UsuarioActual):
    repositorio.responder_observacion_tdr(sesion, actor, expediente_id, observacion_id,
                                         **datos.model_dump())


@router.post("/expedientes/{expediente_id}/lecturas", status_code=201)
def leer_pdf(expediente_id: int, identificador: Annotated[int | None, Depends(usuario_id)], archivo: UploadFile):
    # No se retiene una conexión mientras se espera al proveedor de IA.
    with db.sesion() as sesion:
        actor = actor_actual(sesion, identificador)
        expediente = repositorio.comprobar_cupo_ia(sesion, actor, expediente_id)
        contexto = {"tipo": expediente.tipo, "descripcion": expediente.descripcion,
                    "plazo_dias": expediente.plazo_dias}
    resultado = extractor.extraer(leer_archivo(archivo, extractor.TAMANO_MAXIMO), expediente=contexto)
    with db.sesion() as sesion:
        identificador_lectura = repositorio.registrar_propuesta_ia(
            sesion, actor_actual(sesion, identificador), expediente_id, archivo_nombre=archivo.filename,
            archivo_sha256=resultado.archivo_sha256, propuesta=resultado.propuesta, origen=resultado.origen,
            aviso=resultado.aviso, advertencias=resultado.advertencias,
        )
    return {"id": identificador_lectura}


class Aprobacion(BaseModel):
    descripciones: list[str]


class Rechazo(BaseModel):
    motivo: str = ""


@router.post("/lecturas/{lectura_id}/aprobar")
def aprobar_lectura(lectura_id: int, datos: Aprobacion, sesion: Sesion, actor: UsuarioActual):
    return {"agregados": repositorio.aprobar_extraccion(sesion, actor, lectura_id, datos.descripciones)}


@router.post("/lecturas/{lectura_id}/rechazar", status_code=204)
def rechazar_lectura(lectura_id: int, datos: Rechazo, sesion: Sesion, actor: UsuarioActual):
    repositorio.rechazar_extraccion(sesion, actor, lectura_id, datos.motivo)
