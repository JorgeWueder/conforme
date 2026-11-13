from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text

from conforme import bitacora


def _cargar(sesion, n=5):
    for i in range(1, n + 1):
        bitacora.registrar(
            sesion,
            accion="prueba.evento",
            entidad="prueba",
            entidad_id=i,
            detalle={
                "n": i,
                "monto": Decimal("48000.00"),
                "fecha": date(2026, 9, 29),
                "texto": "Conformidad con ñ y tildes: áéíóú",
                "anidado": {"lista": [1, "dos", None, True]},
            },
            documento_sha256="a" * 64 if i % 2 else None,
        )
    sesion.commit()


def test_cadena_valida_tras_pasar_por_la_base(sesion):
    _cargar(sesion)
    resultado = bitacora.verificar_cadena(sesion)
    assert resultado.integra
    assert resultado.total == 5
    assert resultado.id_roto is None


def test_cadena_vacia_es_integra(sesion):
    assert bitacora.verificar_cadena(sesion).integra


def test_el_primer_registro_parte_del_genesis_y_los_demas_enlazan(sesion):
    _cargar(sesion, 3)
    filas = sesion.execute(text("SELECT hash_anterior, hash FROM bitacora ORDER BY id")).all()
    assert filas[0].hash_anterior == bitacora.HASH_GENESIS
    assert filas[1].hash_anterior == filas[0].hash
    assert filas[2].hash_anterior == filas[1].hash


def test_detecta_modificacion_y_senala_el_registro(sesion):
    _cargar(sesion)
    sesion.execute(text("UPDATE bitacora SET detalle = '{\"n\": 999}' WHERE id = 3"))
    sesion.commit()
    resultado = bitacora.verificar_cadena(sesion)
    assert not resultado.integra
    assert resultado.id_roto == 3


def test_detecta_cambio_de_documento(sesion):
    _cargar(sesion)
    sesion.execute(text("UPDATE bitacora SET documento_sha256 = :h WHERE id = 1"), {"h": "b" * 64})
    sesion.commit()
    assert bitacora.verificar_cadena(sesion).id_roto == 1


def test_detecta_borrado_intermedio(sesion):
    _cargar(sesion)
    sesion.execute(text("DELETE FROM bitacora WHERE id = 3"))
    sesion.commit()
    resultado = bitacora.verificar_cadena(sesion)
    assert not resultado.integra
    assert resultado.id_roto == 4  # el siguiente ya no enlaza


def test_detecta_reordenamiento(sesion):
    _cargar(sesion)
    # Intercambia por completo el contenido de los registros 2 y 3.
    columnas = ("ts, actor_id, accion, entidad, entidad_id, expediente_id, "
                "detalle, documento_sha256, hash_anterior, hash")
    sesion.execute(text(f"CREATE TEMP TABLE copia AS SELECT id, {columnas} FROM bitacora WHERE id IN (2, 3)"))
    sesion.execute(text("DELETE FROM bitacora WHERE id IN (2, 3)"))
    sesion.execute(text(
        f"INSERT INTO bitacora (id, {columnas}) OVERRIDING SYSTEM VALUE "
        f"SELECT 5 - id, {columnas} FROM copia"
    ))
    sesion.execute(text("DROP TABLE copia"))
    sesion.commit()
    resultado = bitacora.verificar_cadena(sesion)
    assert not resultado.integra
    assert resultado.id_roto == 2


def test_no_acepta_float():
    with pytest.raises(TypeError):
        bitacora.calcular_hash(
            bitacora.HASH_GENESIS, bitacora.datetime.now(bitacora.timezone.utc),
            None, "x", "y", None, None, {"monto": 1.5}, None,
        )
