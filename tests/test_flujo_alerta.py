"""Descargo, cierre y escalamiento de alertas, desde el repositorio.

Cada prueba trabaja en una transacción que se revierte al terminar.
"""
from datetime import timedelta

import pytest

from conforme import bitacora, repositorio
from conforme.errores import ErrorValidacion
from conforme.permisos import PermisoDenegado
from datos import caso_estrella
from tests.conftest import actor_de


def _alertas_estrella(sesion, actor):
    exp = repositorio.listar_expedientes(sesion, actor, texto=caso_estrella.CODIGO)[0]
    alertas = repositorio.listar_alertas(sesion, actor, expediente_id=exp["id"])
    return exp, {a["regla"]: a for a in alertas}


def _estado(sesion, actor, alerta_id):
    return next(a["estado"] for a in repositorio.listar_alertas(sesion, actor)
                if a["id"] == alerta_id)


def test_descargo_escalamiento_y_cierre_quedan_en_la_linea_de_tiempo(sesion_sembrada):
    s = sesion_sembrada
    inf1, tes1, oci1 = actor_de(s, "inf1"), actor_de(s, "tes1"), actor_de(s, "oci1")
    exp, alertas = _alertas_estrella(s, tes1)
    r2 = alertas["R2"]["id"]

    repositorio.registrar_descargo(s, inf1, r2, "El proveedor avisó del atraso por escrito.")
    assert _estado(s, tes1, r2) == "con_descargo"
    repositorio.escalar_alerta(s, oci1, r2, "Corresponde revisión de la penalidad.")
    assert _estado(s, tes1, r2) == "escalada"
    assert repositorio.obtener_expediente(s, tes1, exp["id"])["alertas_medias"] == 1
    repositorio.cerrar_alerta(s, tes1, r2, "Se aplicó la penalidad en el pago.")
    assert _estado(s, tes1, r2) == "cerrada"
    assert repositorio.obtener_expediente(s, tes1, exp["id"])["alertas_medias"] == 0

    revisiones = repositorio.revisiones_de_alerta(s, inf1, r2)
    assert [r["tipo"] for r in revisiones] == ["descargo", "escalamiento", "cierre"]
    assert revisiones[2]["texto"] == "Se aplicó la penalidad en el pago."

    acciones = [e["accion"] for e in repositorio.linea_de_tiempo(s, inf1, exp["id"])]
    assert acciones[-3:] == ["alerta.descargo", "alerta.escalada", "alerta.cerrada"]
    assert bitacora.verificar_cadena(s).integra


@pytest.mark.parametrize("texto", ["", "   ", None])
def test_el_motivo_y_el_descargo_son_obligatorios(sesion_sembrada, texto):
    s = sesion_sembrada
    _, alertas = _alertas_estrella(s, actor_de(s, "tes1"))
    r1 = alertas["R1"]["id"]
    with pytest.raises(ErrorValidacion):
        repositorio.cerrar_alerta(s, actor_de(s, "tes1"), r1, texto)
    with pytest.raises(ErrorValidacion):
        repositorio.escalar_alerta(s, actor_de(s, "oci1"), r1, texto)
    with pytest.raises(ErrorValidacion):
        repositorio.registrar_descargo(s, actor_de(s, "inf1"), r1, texto)
    assert _estado(s, actor_de(s, "tes1"), r1) == "abierta"


def test_area_usuaria_no_cierra_ni_escala(sesion_sembrada):
    s = sesion_sembrada
    inf1 = actor_de(s, "inf1")
    _, alertas = _alertas_estrella(s, inf1)
    for accion in (repositorio.cerrar_alerta, repositorio.escalar_alerta):
        with pytest.raises(PermisoDenegado):
            accion(s, inf1, alertas["R1"]["id"], "Me la cierro yo.")


def test_solo_implicado_o_conformante_presentan_descargo(sesion_sembrada):
    s = sesion_sembrada
    _, alertas = _alertas_estrella(s, actor_de(s, "tes1"))
    r4 = alertas["R4"]["id"]
    for username in ("inf2", "tes1", "oci1"):  # ven la alerta, pero no figuran en ella
        with pytest.raises(PermisoDenegado):
            repositorio.registrar_descargo(s, actor_de(s, username), r4, "Opino que está bien.")
    with pytest.raises(PermisoDenegado):  # otra área: ni siquiera la ve
        repositorio.registrar_descargo(s, actor_de(s, "ti1"), r4, "No es mi área.")
    with pytest.raises(PermisoDenegado):
        repositorio.revisiones_de_alerta(s, actor_de(s, "ti1"), r4)


def test_no_se_modifica_una_alerta_cerrada(sesion_sembrada):
    s = sesion_sembrada
    tes1, oci1, inf1 = actor_de(s, "tes1"), actor_de(s, "oci1"), actor_de(s, "inf1")
    _, alertas = _alertas_estrella(s, tes1)
    r1 = alertas["R1"]["id"]
    repositorio.cerrar_alerta(s, tes1, r1, "Evidencia entregada en físico y verificada.")
    with pytest.raises(ErrorValidacion):
        repositorio.cerrar_alerta(s, oci1, r1, "Otra vez.")
    with pytest.raises(ErrorValidacion):
        repositorio.escalar_alerta(s, oci1, r1, "Tarde.")
    with pytest.raises(ErrorValidacion):
        repositorio.registrar_descargo(s, inf1, r1, "Tarde.")


def test_el_implicado_no_cierra_ni_escala_su_propia_alerta(sesion_sembrada):
    """tes1 paga un expediente sin conformidad: R5 lo señala y no puede cerrarla."""
    s = sesion_sembrada
    tes1, tes2, oci1 = actor_de(s, "tes1"), actor_de(s, "tes2"), actor_de(s, "oci1")
    exp = next(x for x in repositorio.listar_expedientes(s, tes1)
               if not x["tiene_conformidad"] and x["alertas_altas"] == 0)
    repositorio.registrar_pago(s, tes1, exp["id"], monto=exp["monto"],
                               fecha_pago=exp["fecha_orden"] + timedelta(days=20))

    alertas = repositorio.listar_alertas(s, tes1, expediente_id=exp["id"])
    assert [a["regla"] for a in alertas] == ["R5"]
    assert alertas[0]["persona_implicada_id"] == tes1.persona_id
    assert repositorio.obtener_expediente(s, tes1, exp["id"])["semaforo"] == "rojo"
    r5 = alertas[0]["id"]

    for accion in (repositorio.cerrar_alerta, repositorio.escalar_alerta):
        with pytest.raises(PermisoDenegado, match="persona implicada"):
            accion(s, tes1, r5, "No pasa nada.")
    assert _estado(s, tes1, r5) == "abierta"

    repositorio.registrar_descargo(s, tes1, r5, "Pago adelantado por orden de la gerencia.")
    repositorio.escalar_alerta(s, tes2, r5, "Lo debe ver auditoría.")
    repositorio.cerrar_alerta(s, oci1, r5, "Se abrió informe de control.")
    assert _estado(s, tes1, r5) == "cerrada"
    acciones = [e["accion"] for e in repositorio.linea_de_tiempo(s, tes1, exp["id"])]
    assert acciones[-5:] == ["pago.registrado", "alerta.generada", "alerta.descargo",
                             "alerta.escalada", "alerta.cerrada"]
