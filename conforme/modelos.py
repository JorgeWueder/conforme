"""Modelos SQLAlchemy. El esquema real lo definen los archivos de migraciones/."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CHAR, BigInteger, Date, DateTime, ForeignKey, LargeBinary, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

ROL_AREA_USUARIA = "area_usuaria"
ROL_TESORERIA = "tesoreria"
ROL_AUDITOR = "auditor"

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
    proveedor_id: Mapped[int] = mapped_column(ForeignKey("proveedor.id"))
    solicitante_id: Mapped[int] = mapped_column(ForeignKey("persona.id"))
    numero_orden: Mapped[str] = mapped_column(Text)
    fecha_requerimiento: Mapped[date] = mapped_column(Date)
    fecha_orden: Mapped[date] = mapped_column(Date)
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
    registrado_por: Mapped[int] = mapped_column(ForeignKey("persona.id"))
    registrado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))


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
