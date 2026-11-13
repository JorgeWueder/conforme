"""Alta de expedientes, conformidad con evidencias y pagos, desde el repositorio.

Cada prueba trabaja en una transacción que se revierte al terminar.
"""
import hashlib
from datetime import date, timedelta

import pytest

from conforme import bitacora, repositorio
from conforme.errores import ErrorValidacion
from conforme.permisos import PermisoDenegado
from tests.conftest import actor_de

PDF = b"%PDF-1.4 acta sintetica"


def _pendiente(sesion, actor):
    """Un expediente del alcance del actor sin conformidad ni pagos."""
    return next(x for x in repositorio.listar_expedientes(sesion, actor)
                if not x["tiene_conformidad"] and x["alertas_altas"] == 0)


def _items(entregables, sin_evidencia=()):
    return [
        {
            "entregable_id": e["id"],
            "cumplido": True,
            "observacion": "",
            "evidencias": [] if e["numero"] in sin_evidencia else [
                {"nombre_archivo": f"acta-{e['numero']}.pdf", "mime": "application/pdf",
                 "contenido": PDF}],
        }
        for e in entregables
    ]


def _registrar(sesion, actor, exp, sin_evidencia=(), **cambios):
    entrega = exp["fecha_entrega_real"] or exp["fecha_orden"] + timedelta(days=10)
    datos = dict(fecha_entrega_real=entrega, fecha_conformidad=entrega + timedelta(days=1),
                 penalidad_aplicada="0.00",
                 items=_items(repositorio.listar_entregables(sesion, actor, exp["id"]),
                              sin_evidencia))
    datos.update(cambios)
    return repositorio.registrar_conformidad(sesion, actor, exp["id"], **datos)


def test_conformidad_completa_no_alerta_y_queda_en_bitacora(sesion_sembrada):
    s = sesion_sembrada
    inf2 = actor_de(s, "inf2")
    exp = next(x for x in repositorio.listar_expedientes(s, inf2)
               if not x["tiene_conformidad"] and x["alertas_altas"] == 0
               and x["solicitante_id"] != inf2.persona_id)
    _registrar(s, inf2, exp)

    conformidad = repositorio.obtener_conformidad(s, inf2, exp["id"])
    assert conformidad["conformante_id"] == inf2.persona_id
    entregables = repositorio.listar_entregables(s, inf2, exp["id"])
    assert all(e["cumplido"] and len(e["evidencias"]) == 1 for e in entregables)
    assert repositorio.listar_alertas(s, inf2, expediente_id=exp["id"]) == []
    assert repositorio.obtener_expediente(s, inf2, exp["id"])["semaforo"] == "verde"

    evidencia = entregables[0]["evidencias"][0]
    archivo = repositorio.obtener_evidencia(s, inf2, evidencia["id"])
    assert bytes(archivo["contenido"]) == PDF
    assert evidencia["sha256"] == hashlib.sha256(PDF).hexdigest()

    eventos = repositorio.linea_de_tiempo(s, inf2, exp["id"])
    nuevos = [e for e in eventos if e["accion"] in ("conformidad.registrada", "evidencia.adjuntada")]
    assert [e["accion"] for e in nuevos] == (
        ["conformidad.registrada"] + ["evidencia.adjuntada"] * len(entregables))
    assert {e["documento_sha256"] for e in nuevos[1:]} == {evidencia["sha256"]}
    assert bitacora.verificar_cadena(s).integra


def test_se_puede_guardar_sin_evidencia_y_eso_genera_r1(sesion_sembrada):
    s = sesion_sembrada
    inf1 = actor_de(s, "inf1")
    exp = _pendiente(s, inf1)
    _registrar(s, inf1, exp, sin_evidencia={1})
    reglas = {a["regla"] for a in repositorio.listar_alertas(s, inf1, expediente_id=exp["id"])}
    esperadas = {"R1"} | ({"R4"} if exp["solicitante_id"] == inf1.persona_id else set())
    assert reglas == esperadas
    assert repositorio.obtener_expediente(s, inf1, exp["id"])["semaforo"] == "rojo"
    acciones = [e["accion"] for e in repositorio.linea_de_tiempo(s, inf1, exp["id"])]
    assert acciones.count("alerta.generada") == len(esperadas)


def test_una_sola_conformidad_por_expediente(sesion_sembrada):
    s = sesion_sembrada
    inf1 = actor_de(s, "inf1")
    exp = _pendiente(s, inf1)
    _registrar(s, inf1, exp)
    with pytest.raises(ErrorValidacion, match="ya tiene una conformidad"):
        _registrar(s, inf1, exp)


def test_validaciones_de_la_conformidad(sesion_sembrada):
    s = sesion_sembrada
    inf1 = actor_de(s, "inf1")
    exp = _pendiente(s, inf1)
    entregables = repositorio.listar_entregables(s, inf1, exp["id"])
    entrega = exp["fecha_orden"] + timedelta(days=10)
    with pytest.raises(ErrorValidacion, match="cada entregable"):
        _registrar(s, inf1, exp, items=_items(entregables[:-1]))
    with pytest.raises(ErrorValidacion, match="anterior a la entrega"):
        _registrar(s, inf1, exp, fecha_entrega_real=entrega,
                   fecha_conformidad=entrega - timedelta(days=1))
    with pytest.raises(ErrorValidacion, match="Penalidad"):
        _registrar(s, inf1, exp, penalidad_aplicada="-1")
    malos = _items(entregables)
    malos[0]["evidencias"] = [{"nombre_archivo": "x.exe", "mime": "application/x-msdownload",
                               "contenido": b"MZ"}]
    with pytest.raises(ErrorValidacion, match="no admitido"):
        _registrar(s, inf1, exp, items=malos)
    assert repositorio.obtener_conformidad(s, inf1, exp["id"]) is None


def test_tesoreria_y_auditor_no_registran_conformidades(sesion_sembrada):
    s = sesion_sembrada
    exp = _pendiente(s, actor_de(s, "inf1"))
    for username in ("tes1", "oci1"):
        with pytest.raises(PermisoDenegado):
            _registrar(s, actor_de(s, username), exp)
    assert repositorio.obtener_conformidad(s, actor_de(s, "tes1"), exp["id"]) is None


def test_area_usuaria_no_da_conformidad_a_expedientes_de_otra_area(sesion_sembrada):
    s = sesion_sembrada
    exp = _pendiente(s, actor_de(s, "inf1"))
    ti1 = actor_de(s, "ti1")
    with pytest.raises(PermisoDenegado):
        repositorio.registrar_conformidad(
            s, ti1, exp["id"], fecha_conformidad=date(2026, 11, 2), penalidad_aplicada="0",
            items=[], fecha_entrega_real=date(2026, 11, 1))
    for lectura in (repositorio.listar_entregables, repositorio.obtener_conformidad,
                    repositorio.listar_pagos):
        with pytest.raises(PermisoDenegado):
            lectura(s, ti1, exp["id"])


def test_evidencia_de_otra_area_no_se_entrega(sesion_sembrada):
    s = sesion_sembrada
    inf1, ti1, tes1 = actor_de(s, "inf1"), actor_de(s, "ti1"), actor_de(s, "tes1")
    exp = next(x for x in repositorio.listar_expedientes(s, inf1) if x["tiene_conformidad"])
    evidencia = next(ev for e in repositorio.listar_entregables(s, inf1, exp["id"])
                     for ev in e["evidencias"])
    assert repositorio.obtener_evidencia(s, inf1, evidencia["id"]) is not None
    assert repositorio.obtener_evidencia(s, tes1, evidencia["id"]) is not None
    assert repositorio.obtener_evidencia(s, ti1, evidencia["id"]) is None


def test_alertas_visibles_segun_el_alcance(sesion_sembrada):
    s = sesion_sembrada
    assert len(repositorio.listar_alertas(s, actor_de(s, "tes1"))) == 28
    assert len(repositorio.listar_alertas(s, actor_de(s, "oci1"))) == 28
    propias = repositorio.listar_alertas(s, actor_de(s, "inf1"))
    assert 3 <= len(propias) < 28
    assert {a["area_sigla"] for a in propias} == {"INF"}


def test_solo_tesoreria_registra_pagos(sesion_sembrada):
    s = sesion_sembrada
    exp = next(x for x in repositorio.listar_expedientes(s, actor_de(s, "inf1"))
               if x["tiene_conformidad"] and x["semaforo"] == "verde")
    for username in ("inf1", "oci1"):
        with pytest.raises(PermisoDenegado):
            repositorio.registrar_pago(s, actor_de(s, username), exp["id"],
                                       fecha_pago=date(2026, 11, 10), monto=exp["monto"])
    tes1 = actor_de(s, "tes1")
    antes = len(repositorio.listar_pagos(s, tes1, exp["id"]))
    with pytest.raises(ErrorValidacion):
        repositorio.registrar_pago(s, tes1, exp["id"], fecha_pago=date(2026, 11, 10), monto=0)
    # Pago posterior a la conformidad: no alerta.
    repositorio.registrar_pago(s, tes1, exp["id"], fecha_pago=date(2026, 11, 20),
                               monto=exp["monto"])
    assert len(repositorio.listar_pagos(s, tes1, exp["id"])) == antes + 1
    assert repositorio.listar_alertas(s, tes1, expediente_id=exp["id"]) == []


def test_auditor_no_reevalua(sesion_sembrada):
    s = sesion_sembrada
    oci1 = actor_de(s, "oci1")
    with pytest.raises(PermisoDenegado):
        repositorio.reevaluar(s, oci1, repositorio.listar_expedientes(s, oci1)[0]["id"])


def _datos_expediente(sesion, actor, **cambios):
    datos = dict(
        tipo="servicio", descripcion="Servicio de prueba", numero_orden="OS-2026-00301",
        proveedor_id=repositorio.listar_proveedores(sesion, actor)[0]["id"],
        fecha_requerimiento=date(2026, 11, 2), fecha_orden=date(2026, 11, 9),
        fecha_inicio_prestacion=date(2026, 11, 10), plazo_dias=30, monto="12500.50",
        entregables=[{"numero": 2, "descripcion": "Informe final"},
                     {"numero": 1, "descripcion": "Plan de trabajo"}],
    )
    datos.update(cambios)
    return datos


def test_area_usuaria_crea_expediente_con_entregables(sesion_sembrada):
    s = sesion_sembrada
    inf1 = actor_de(s, "inf1")
    nuevo = repositorio.crear_expediente(s, inf1, **_datos_expediente(s, inf1))
    exp = repositorio.obtener_expediente(s, inf1, nuevo)
    assert exp["codigo"] == "EXP-2026-0301"
    assert exp["area_sigla"] == "INF" and exp["solicitante_id"] == inf1.persona_id
    assert str(exp["monto"]) == "12500.50" and exp["semaforo"] == "verde"
    entregables = repositorio.listar_entregables(s, inf1, nuevo)
    assert [(e["numero"], e["descripcion"], e["cumplido"]) for e in entregables] == [
        (1, "Plan de trabajo", None), (2, "Informe final", None)]
    assert [e["accion"] for e in repositorio.linea_de_tiempo(s, inf1, nuevo)] == [
        "expediente.registrado"]
    assert repositorio.obtener_expediente(s, actor_de(s, "tes1"), nuevo) is not None
    assert repositorio.obtener_expediente(s, actor_de(s, "ti1"), nuevo) is None


@pytest.mark.parametrize("cambios, fragmento", [
    ({"plazo_dias": 0}, "plazo"),
    ({"monto": "0"}, "Monto"),
    ({"descripcion": "  "}, "descripción"),
    ({"entregables": []}, "al menos un entregable"),
    ({"entregables": [{"numero": 1, "descripcion": "A"}, {"numero": 1, "descripcion": "B"}]},
     "repetido"),
    ({"fecha_orden": date(2026, 10, 1)}, "anterior al requerimiento"),
    ({"proveedor_id": 999999}, "proveedor"),
])
def test_validaciones_del_expediente(sesion_sembrada, cambios, fragmento):
    s = sesion_sembrada
    inf1 = actor_de(s, "inf1")
    with pytest.raises(ErrorValidacion, match=fragmento):
        repositorio.crear_expediente(s, inf1, **_datos_expediente(s, inf1, **cambios))


@pytest.mark.parametrize("username", ["tes1", "oci1"])
def test_solo_area_usuaria_crea_expedientes(sesion_sembrada, username):
    s = sesion_sembrada
    actor = actor_de(s, username)
    with pytest.raises(PermisoDenegado):
        repositorio.crear_expediente(s, actor, **_datos_expediente(s, actor))
