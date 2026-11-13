"""Bitácora de acciones encadenada por hash.

Cada registro guarda el hash del anterior. El hash se calcula sobre un JSON
canónico (claves ordenadas, fechas y montos como texto) para que la
verificación sea reproducible después de pasar por la base de datos.

Límite conocido: una cadena por sí sola no detecta el borrado de los ÚLTIMOS
registros. El sello de la conformidad (fase 3) guarda el hash vigente y cubre
ese caso.
"""
import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import insert, select, text
from sqlalchemy.orm import Session

from conforme.modelos import Bitacora

HASH_GENESIS = "0" * 64
_CANDADO = 20261125  # clave del candado asesor: serializa las inserciones


def _normalizar(valor):
    """Deja solo tipos que JSONB devuelve idénticos: texto, enteros, bool, null."""
    if valor is None or isinstance(valor, (bool, int, str)):
        return valor
    if isinstance(valor, float):
        raise TypeError("La bitácora no acepta float; usa Decimal o texto.")
    if isinstance(valor, datetime):
        return _ts_texto(valor)
    if isinstance(valor, (Decimal, date)):
        return str(valor)
    if isinstance(valor, dict):
        return {str(k): _normalizar(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_normalizar(v) for v in valor]
    raise TypeError(f"Tipo no admitido en la bitácora: {type(valor).__name__}")


def _ts_texto(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def calcular_hash(
    hash_anterior: str,
    ts: datetime,
    actor_id: int | None,
    accion: str,
    entidad: str,
    entidad_id: int | None,
    expediente_id: int | None,
    detalle: dict,
    documento_sha256: str | None,
) -> str:
    cuerpo = {
        "hash_anterior": hash_anterior,
        "ts": _ts_texto(ts),
        "actor_id": actor_id,
        "accion": accion,
        "entidad": entidad,
        "entidad_id": entidad_id,
        "expediente_id": expediente_id,
        "detalle": _normalizar(detalle),
        "documento_sha256": documento_sha256,
    }
    canonico = json.dumps(cuerpo, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def registrar_lote(sesion: Session, eventos: list[dict]) -> None:
    """Añade varios registros encadenados, en el orden recibido.

    Cada evento: accion, entidad y, opcionales, actor_id, entidad_id,
    expediente_id, detalle, documento_sha256, ts.
    """
    if not eventos:
        return
    # El candado dura hasta el fin de la transacción: dos sesiones no pueden
    # leer el mismo "último hash" y bifurcar la cadena.
    sesion.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _CANDADO})
    anterior = sesion.execute(
        select(Bitacora.hash).order_by(Bitacora.id.desc()).limit(1)
    ).scalar_one_or_none() or HASH_GENESIS

    filas = []
    for evento in eventos:
        fila = {
            "ts": evento.get("ts") or datetime.now(timezone.utc),
            "actor_id": evento.get("actor_id"),
            "accion": evento["accion"],
            "entidad": evento["entidad"],
            "entidad_id": evento.get("entidad_id"),
            "expediente_id": evento.get("expediente_id"),
            "detalle": _normalizar(evento.get("detalle") or {}),
            "documento_sha256": evento.get("documento_sha256"),
        }
        fila["hash_anterior"] = anterior
        fila["hash"] = calcular_hash(**fila)
        anterior = fila["hash"]
        filas.append(fila)
    sesion.execute(insert(Bitacora), filas)


def registrar(sesion: Session, **evento) -> None:
    registrar_lote(sesion, [evento])


@dataclass(frozen=True)
class ResultadoVerificacion:
    integra: bool
    total: int
    id_roto: int | None = None
    motivo: str | None = None


def verificar_cadena(sesion: Session) -> ResultadoVerificacion:
    """Recorre la bitácora en orden y devuelve el primer registro que no cuadra."""
    registros = sesion.execute(select(Bitacora).order_by(Bitacora.id)).scalars().all()
    anterior = HASH_GENESIS
    for r in registros:
        if r.hash_anterior != anterior:
            return ResultadoVerificacion(
                False, len(registros), r.id,
                "No enlaza con el registro anterior: falta un registro, se cambió "
                "el orden o se alteró el hash del anterior.",
            )
        esperado = calcular_hash(
            r.hash_anterior, r.ts, r.actor_id, r.accion, r.entidad,
            r.entidad_id, r.expediente_id, r.detalle, r.documento_sha256,
        )
        if esperado != r.hash:
            return ResultadoVerificacion(
                False, len(registros), r.id,
                "El contenido del registro no coincide con su hash: fue modificado.",
            )
        anterior = r.hash
    return ResultadoVerificacion(True, len(registros))
