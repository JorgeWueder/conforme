"""Modelos SQLAlchemy. El esquema real lo definen los archivos de migraciones/."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CHAR, BigInteger, Boolean, Date, DateTime, ForeignKey, LargeBinary, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

ROL_AREA_USUARIA = "area_usuaria"
ROL_TESORERIA = "tesoreria"
ROL_AUDITOR = "auditor"
ROL_ABASTECIMIENTO = "abastecimiento"

ESTADO_ABIERTA = "abierta"
ESTADO_CON_DESCARGO = "con_descargo"
ESTADO_CERRADA = "cerrada"
ESTADO_ESCALADA = "escalada"


class Base(DeclarativeBase):
    pass


class Area(Base):
    __tablename__ = "area"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    nombre: Mapped[str] = mapped_column(Text)
    sigla: Mapped[str] = mapped_column(Text)


class Persona(Base):
    __tablename__ = "persona"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    dni: Mapped[str] = mapped_column(CHAR(8))
    nombres: Mapped[str] = mapped_column(Text)
    apellidos: Mapped[str] = mapped_column(Text)
    cargo: Mapped[str] = mapped_column(Text)
    area_id: Mapped[int] = mapped_column(ForeignKey("area.id"))


class Usuario(Base):
    __tablename__ = "usuario"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    persona_id: Mapped[int] = mapped_column(ForeignKey("persona.id"))
    username: Mapped[str] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text)
    rol: Mapped[str] = mapped_column(Text)


class Proveedor(Base):
    __tablename__ = "proveedor"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ruc: Mapped[str] = mapped_column(CHAR(11))
    razon_social: Mapped[str] = mapped_column(Text)


class Expediente(Base):
    __tablename__ = "expediente"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    codigo: Mapped[str] = mapped_column(Text)
    tipo: Mapped[str] = mapped_column(Text)
    descripcion: Mapped[str] = mapped_column(Text)
    area_id: Mapped[int] = mapped_column(ForeignKey("area.id"))
    proveedor_id: Mapped[int | None] = mapped_column(ForeignKey("proveedor.id"))
    solicitante_id: Mapped[int] = mapped_column(ForeignKey("persona.id"))
    numero_orden: Mapped[str | None] = mapped_column(Text)
    estado_flujo: Mapped[str] = mapped_column(Text, server_default="en_ejecucion")
    proyecto_referencia: Mapped[str | None] = mapped_column(Text)
    conformidad_plazo_especial: Mapped[bool] = mapped_column(server_default="false")
    fecha_requerimiento: Mapped[date] = mapped_column(Date)
    fecha_orden: Mapped[date | None] = mapped_column(Date)
    fecha_inicio_prestacion: Mapped[date | None] = mapped_column(Date)
    plazo_dias: Mapped[int]
    fecha_entrega_real: Mapped[date | None] = mapped_column(Date)
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Bitacora(Base):
    __tablename__ = "bitacora"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("persona.id"))
    accion: Mapped[str] = mapped_column(Text)
    entidad: Mapped[str] = mapped_column(Text)
    entidad_id: Mapped[int | None] = mapped_column(BigInteger)
    expediente_id: Mapped[int | None] = mapped_column(ForeignKey("expediente.id"))
    detalle: Mapped[dict] = mapped_column(JSONB)
    documento_sha256: Mapped[str | None] = mapped_column(CHAR(64))
    hash_anterior: Mapped[str] = mapped_column(CHAR(64))
    hash: Mapped[str] = mapped_column(CHAR(64))


class Entregable(Base):
    __tablename__ = "entregable"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    expediente_id: Mapped[int] = mapped_column(ForeignKey("expediente.id"))
    numero: Mapped[int]
    descripcion: Mapped[str] = mapped_column(Text)
    origen: Mapped[str] = mapped_column(Text)
    criterio_evidencia: Mapped[str | None] = mapped_column(Text)


class Conformidad(Base):
    __tablename__ = "conformidad"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    expediente_id: Mapped[int] = mapped_column(ForeignKey("expediente.id"))
    conformante_id: Mapped[int] = mapped_column(ForeignKey("persona.id"))
    fecha_conformidad: Mapped[date] = mapped_column(Date)
    observaciones: Mapped[str] = mapped_column(Text)
    penalidad_aplicada: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    codigo_sello: Mapped[str | None] = mapped_column(Text)
    sello_bitacora_id: Mapped[int | None] = mapped_column(BigInteger)
    sello_hash: Mapped[str | None] = mapped_column(CHAR(64))
    registrada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(server_default="1")
    vigente: Mapped[bool] = mapped_column(Boolean, server_default="true")
    sustento_penalidad: Mapped[str | None] = mapped_column(Text)
    verificacion_evidencias: Mapped[dict | None] = mapped_column(JSONB)
    estado_revision_dec: Mapped[str] = mapped_column(Text, server_default="pendiente")
    referencia_derivacion: Mapped[str | None] = mapped_column(Text)
    motivo_revision_dec: Mapped[str | None] = mapped_column(Text)
    revisado_dec_por: Mapped[int | None] = mapped_column(ForeignKey("persona.id"))
    revisado_dec_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ConformidadEntregable(Base):
    __tablename__ = "conformidad_entregable"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conformidad_id: Mapped[int] = mapped_column(ForeignKey("conformidad.id"))
    entregable_id: Mapped[int] = mapped_column(ForeignKey("entregable.id"))
    cumplido: Mapped[bool]
    observacion: Mapped[str] = mapped_column(Text)


class Evidencia(Base):
    __tablename__ = "evidencia"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conformidad_entregable_id: Mapped[int] = mapped_column(ForeignKey("conformidad_entregable.id"))
    nombre_archivo: Mapped[str] = mapped_column(Text)
    mime: Mapped[str] = mapped_column(Text)
    tamano: Mapped[int]
    sha256: Mapped[str] = mapped_column(CHAR(64))
    contenido: Mapped[bytes] = mapped_column(LargeBinary)
    subido_por: Mapped[int] = mapped_column(ForeignKey("persona.id"))
    subido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Pago(Base):
    __tablename__ = "pago"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    expediente_id: Mapped[int] = mapped_column(ForeignKey("expediente.id"))
    fecha_pago: Mapped[date] = mapped_column(Date)
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    penalidad_descontada: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    referencia_siaf: Mapped[str | None] = mapped_column(Text)
    registrado_por: Mapped[int] = mapped_column(ForeignKey("persona.id"))
    registrado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    verificacion_pago_id: Mapped[int | None] = mapped_column(ForeignKey("verificacion_pago.id"))


class Alerta(Base):
    __tablename__ = "alerta"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    expediente_id: Mapped[int] = mapped_column(ForeignKey("expediente.id"))
    regla: Mapped[str] = mapped_column(Text)
    clave: Mapped[str] = mapped_column(Text)
    severidad: Mapped[str] = mapped_column(Text)
    explicacion: Mapped[str] = mapped_column(Text)
    datos: Mapped[dict] = mapped_column(JSONB)
    persona_implicada_id: Mapped[int | None] = mapped_column(ForeignKey("persona.id"))
    estado: Mapped[str] = mapped_column(Text)
    ambito: Mapped[str] = mapped_column(Text, server_default="operativa_tesoreria")
    bloqueante: Mapped[bool] = mapped_column(Boolean, server_default="false")
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actualizada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AlertaRevision(Base):
    __tablename__ = "alerta_revision"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    alerta_id: Mapped[int] = mapped_column(ForeignKey("alerta.id"))
    tipo: Mapped[str] = mapped_column(Text)
    autor_id: Mapped[int] = mapped_column(ForeignKey("persona.id"))
    texto: Mapped[str] = mapped_column(Text)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ExtraccionIA(Base):
    __tablename__ = "extraccion_ia"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    expediente_id: Mapped[int] = mapped_column(ForeignKey("expediente.id"))
    archivo_nombre: Mapped[str] = mapped_column(Text)
    archivo_sha256: Mapped[str] = mapped_column(CHAR(64))
    resultado: Mapped[dict] = mapped_column(JSONB)
    origen: Mapped[str] = mapped_column(Text)
    aviso: Mapped[str | None] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(Text)
    creado_por: Mapped[int] = mapped_column(ForeignKey("persona.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revisado_por: Mapped[int | None] = mapped_column(ForeignKey("persona.id"))
    revisado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RevisionPrevia(Base):
    __tablename__ = "revision_previa"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    asignado_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expediente_id: Mapped[int | None] = mapped_column(ForeignKey("expediente.id"))
    evaluador_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    revisor_independiente_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    estado_revision_independiente: Mapped[str | None] = mapped_column(Text)
    comentario_revision_independiente: Mapped[str | None] = mapped_column(Text)
    enviado_revision_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revisado_independiente_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    proveedor_seleccionado_ruc: Mapped[str | None] = mapped_column(CHAR(11))
    sustento_seleccion: Mapped[str | None] = mapped_column(Text)


class RevisionPreviaVersion(Base):
    __tablename__ = "revision_previa_version"
    revision_id: Mapped[int] = mapped_column(ForeignKey("revision_previa.id"), primary_key=True)
    numero: Mapped[int] = mapped_column(primary_key=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    contenido: Mapped[dict] = mapped_column(JSONB)


class PrevencionEdicion(Base):
    __tablename__ = "prevencion_edicion"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    fuente: Mapped[str] = mapped_column(Text)
    fecha_corte: Mapped[date] = mapped_column(Date)
    descargado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sha256: Mapped[str] = mapped_column(CHAR(64))
    alcance: Mapped[str] = mapped_column(Text)
    manifiesto: Mapped[dict] = mapped_column(JSONB)


class PrevencionRegistro(Base):
    __tablename__ = "prevencion_registro"
    edicion_id: Mapped[int] = mapped_column(ForeignKey("prevencion_edicion.id"), primary_key=True)
    fila: Mapped[int] = mapped_column(primary_key=True)
    ruc: Mapped[str] = mapped_column(CHAR(11))
    datos: Mapped[dict] = mapped_column(JSONB)


class ExpedientePostor(Base):
    __tablename__ = "expediente_postor"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    expediente_id: Mapped[int] = mapped_column(ForeignKey("expediente.id"))
    ruc: Mapped[str] = mapped_column(CHAR(11))
    razon_social: Mapped[str] = mapped_column(Text)
    monto_cotizado: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    plazo_dias: Mapped[int]
    contacto_nombre: Mapped[str | None] = mapped_column(Text)
    contacto_correo: Mapped[str | None] = mapped_column(Text)
    contacto_telefono: Mapped[str | None] = mapped_column(Text)
    direccion: Mapped[str | None] = mapped_column(Text)
    proforma_ref: Mapped[str | None] = mapped_column(Text)
    cumple_tdr: Mapped[bool | None] = mapped_column(Boolean)
    estado: Mapped[str] = mapped_column(Text, server_default="pendiente")
    motivo_descarte: Mapped[str | None] = mapped_column(Text)
    analisis_dimensiones: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    informe_consolidado: Mapped[dict | None] = mapped_column(JSONB)
    notas_encargado: Mapped[str] = mapped_column(Text, server_default="")
    registrado_por: Mapped[int] = mapped_column(ForeignKey("persona.id"))
    analizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consolidado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RevisionDocumental(Base):
    __tablename__ = "revision_documental"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ambito: Mapped[str] = mapped_column(Text)
    expediente_id: Mapped[int | None] = mapped_column(ForeignKey("expediente.id"))
    postor_id: Mapped[int | None] = mapped_column(ForeignKey("expediente_postor.id"))
    archivos: Mapped[list] = mapped_column(JSONB, server_default="[]")
    resultados_bloques: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    benford: Mapped[dict | None] = mapped_column(JSONB)
    veredicto: Mapped[str | None] = mapped_column(Text)
    resumen_agente: Mapped[str | None] = mapped_column(Text)
    creado_por: Mapped[int] = mapped_column(ForeignKey("persona.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TdrObservacion(Base):
    __tablename__ = "tdr_observacion"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    expediente_id: Mapped[int] = mapped_column(ForeignKey("expediente.id"))
    origen: Mapped[str] = mapped_column(Text)
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("persona.id"))
    detalle: Mapped[str] = mapped_column(Text)
    severidad: Mapped[str] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(Text, server_default="pendiente")
    respuesta_area: Mapped[str | None] = mapped_column(Text)
    respondido_por: Mapped[int | None] = mapped_column(ForeignKey("persona.id"))
    respondido_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ConflictoInteres(Base):
    __tablename__ = "conflicto_interes"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    expediente_id: Mapped[int] = mapped_column(ForeignKey("expediente.id"))
    revision_previa_id: Mapped[int | None] = mapped_column(ForeignKey("revision_previa.id"))
    persona_id: Mapped[int] = mapped_column(ForeignKey("persona.id"))
    proveedor_ruc: Mapped[str | None] = mapped_column(CHAR(11))
    tipo: Mapped[str] = mapped_column(Text)
    descripcion: Mapped[str] = mapped_column(Text)
    bloqueante: Mapped[bool] = mapped_column(Boolean, server_default="false")
    estado: Mapped[str] = mapped_column(Text, server_default="declarado")
    registrado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class VerificacionPago(Base):
    __tablename__ = "verificacion_pago"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    expediente_id: Mapped[int] = mapped_column(ForeignKey("expediente.id"))
    verificado_por: Mapped[int] = mapped_column(ForeignKey("persona.id"))
    checklist: Mapped[dict] = mapped_column(JSONB)
    bloqueos_activos: Mapped[list] = mapped_column(JSONB, server_default="[]")
    apto_para_pago: Mapped[bool] = mapped_column(Boolean)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ActuacionOCI(Base):
    __tablename__ = "actuacion_oci"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    entidad: Mapped[str] = mapped_column(Text)
    entidad_id: Mapped[int] = mapped_column(BigInteger)
    tipo: Mapped[str] = mapped_column(Text)
    descripcion: Mapped[str] = mapped_column(Text)
    autor_id: Mapped[int] = mapped_column(ForeignKey("persona.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DocumentoPostor(Base):
    __tablename__ = "documento_postor"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    expediente_id: Mapped[int] = mapped_column(ForeignKey("expediente.id"))
    postor_id: Mapped[int] = mapped_column(ForeignKey("expediente_postor.id"))
    tipo: Mapped[str] = mapped_column(Text)
    nombre_archivo: Mapped[str] = mapped_column(Text)
    mime: Mapped[str] = mapped_column(Text)
    tamano: Mapped[int]
    sha256: Mapped[str] = mapped_column(CHAR(64))
    contenido: Mapped[bytes] = mapped_column(LargeBinary)
    subido_por: Mapped[int] = mapped_column(ForeignKey("persona.id"))
    subido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
