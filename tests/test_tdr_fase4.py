"""Compuerta del TDR y respuesta a observaciones antes de evaluar proveedores."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import app
from conforme import db, repositorio
from conforme.errores import ErrorValidacion
from conforme.ia.extractor import EntregableIA, PropuestaIA
from conforme.modelos import Expediente
from conforme.permisos import PermisoDenegado
from conforme.proveedores import repositorio as evaluacion
from tests.conftest import PASSWORD_PRUEBA, actor_de


def _nuevo(sesion, area):
    return repositorio.crear_requerimiento(
        sesion, area, tipo="servicio", descripcion="Mantenimiento de equipos informáticos",
        fecha_requerimiento=date.today(), plazo_dias=30, monto="1500.00",
        entregables=[], origen_entregables="tdr")


def _aprobar(sesion, area, expediente_id, *, origen="modelo", corresponde=True):
    propuesta = PropuestaIA(
        objeto="Mantenimiento de equipos informáticos" if corresponde else "Compra de muebles",
        corresponde_al_expediente=corresponde,
        motivo_discrepancia="El documento trata de muebles" if not corresponde else "",
        plazo_dias=30,
        entregables=[EntregableIA(numero=1, descripcion="Informe técnico del mantenimiento")])
    lectura_id = repositorio.registrar_propuesta_ia(
        sesion, area, expediente_id, archivo_nombre="tdr.pdf", archivo_sha256="a" * 64,
        propuesta=propuesta, origen=origen, aviso=None)
    repositorio.aprobar_extraccion(sesion, area, lectura_id, ["Informe técnico del mantenimiento"])


def test_tdr_real_habilita_evaluacion_y_observacion_la_bloquea(sesion_sembrada):
    sesion = sesion_sembrada
    area, dec = actor_de(sesion, "inf1"), actor_de(sesion, "dec1")
    expediente_id = _nuevo(sesion, area)
    assert sesion.get(Expediente, expediente_id).estado_flujo == "requerimiento"
    with pytest.raises(ErrorValidacion, match="ya no está en evaluación"):
        evaluacion.analizar(sesion, dec, expediente_id)
    _aprobar(sesion, area, expediente_id)
    assert repositorio.estado_tdr(sesion, area, expediente_id) == {"analizado": True, "pendientes": 0}
    assert sesion.get(Expediente, expediente_id).estado_flujo == "en_evaluacion_proveedores"

    repositorio.registrar_observacion_tdr(
        sesion, dec, expediente_id, detalle="Precisar los equipos incluidos", severidad="bloqueante")
    assert sesion.get(Expediente, expediente_id).estado_flujo == "tdr_observado"
    with pytest.raises(ErrorValidacion, match="ya no está en evaluación"):
        evaluacion.analizar(sesion, dec, expediente_id)
    observacion = repositorio.listar_observaciones_tdr(sesion, area, expediente_id)[0]
    with pytest.raises(ErrorValidacion, match="TDR corregido"):
        repositorio.responder_observacion_tdr(
            sesion, area, expediente_id, observacion["id"], estado="corregida",
            respuesta="Se corrigió el plazo.")
    repositorio.responder_observacion_tdr(
        sesion, area, expediente_id, observacion["id"], estado="justificada",
        respuesta="El anexo 1 contiene el inventario de equipos.")
    assert sesion.get(Expediente, expediente_id).estado_flujo == "en_evaluacion_proveedores"
    assert repositorio.estado_tdr(sesion, dec, expediente_id)["pendientes"] == 0


def test_entregables_manuales_no_se_duplican_al_aprobar_tdr(sesion_sembrada):
    sesion = sesion_sembrada
    area = actor_de(sesion, "inf1")
    expediente_id = repositorio.crear_requerimiento(
        sesion, area, tipo="servicio", descripcion="Mantenimiento de equipos informáticos",
        fecha_requerimiento=date.today(), plazo_dias=30, monto="1500.00",
        entregables=[{"numero": 1, "descripcion": "Informe técnico del mantenimiento"}])
    propuesta = PropuestaIA(objeto="Mantenimiento de equipos informáticos",
                           corresponde_al_expediente=True,
                           entregables=[EntregableIA(numero=1, descripcion="Informe técnico del mantenimiento")])
    lectura_id = repositorio.registrar_propuesta_ia(
        sesion, area, expediente_id, archivo_nombre="tdr.pdf", archivo_sha256="d" * 64,
        propuesta=propuesta, origen="modelo", aviso=None)
    assert repositorio.aprobar_extraccion(sesion, area, lectura_id, []) == 0
    assert len(repositorio.listar_entregables(sesion, area, expediente_id)) == 1
    assert sesion.get(Expediente, expediente_id).estado_flujo == "en_evaluacion_proveedores"


def test_ejemplo_no_habilita_y_discrepancia_real_crea_observacion(sesion_sembrada):
    sesion = sesion_sembrada
    area, dec = actor_de(sesion, "inf1"), actor_de(sesion, "dec1")
    expediente_id = _nuevo(sesion, area)
    _aprobar(sesion, area, expediente_id, origen="respaldo")
    assert sesion.get(Expediente, expediente_id).estado_flujo == "requerimiento"
    assert not repositorio.estado_tdr(sesion, area, expediente_id)["analizado"]
    with pytest.raises(PermisoDenegado):
        repositorio.registrar_observacion_tdr(
            sesion, area, expediente_id, detalle="Prueba", severidad="bloqueante")

    # La propuesta posterior no repite el entregable ya añadido por el ejemplo.
    propuesta = PropuestaIA(objeto="Compra de muebles", corresponde_al_expediente=False,
                           motivo_discrepancia="El documento trata de muebles",
                           entregables=[EntregableIA(numero=1, descripcion="Acta de instalación")])
    lectura_id = repositorio.registrar_propuesta_ia(
        sesion, area, expediente_id, archivo_nombre="otro.pdf", archivo_sha256="b" * 64,
        propuesta=propuesta, origen="modelo", aviso=None)
    repositorio.aprobar_extraccion(sesion, area, lectura_id, ["Acta de instalación"])
    assert sesion.get(Expediente, expediente_id).estado_flujo == "tdr_observado"
    obs = repositorio.listar_observaciones_tdr(sesion, dec, expediente_id)
    assert len(obs) == 1 and obs[0]["origen"] == "ia"
    corregido = PropuestaIA(objeto="Mantenimiento de equipos informáticos",
                            corresponde_al_expediente=True,
                            entregables=[EntregableIA(numero=1, descripcion="Acta de cierre")])
    lectura_id = repositorio.registrar_propuesta_ia(
        sesion, area, expediente_id, archivo_nombre="tdr-corregido.pdf",
        archivo_sha256="c" * 64, propuesta=corregido, origen="modelo", aviso=None)
    repositorio.aprobar_extraccion(sesion, area, lectura_id, ["Acta de cierre"])
    repositorio.responder_observacion_tdr(
        sesion, area, expediente_id, obs[0]["id"], estado="corregida",
        respuesta="Se reemplazó el TDR y se precisó el objeto del servicio.")
    assert sesion.get(Expediente, expediente_id).estado_flujo == "en_evaluacion_proveedores"


def test_recorrido_http_de_observacion_y_respuesta(engine, base_sembrada, monkeypatch):
    monkeypatch.setattr(db, "_engine", engine)
    with TestClient(app, headers={"X-Conforme": "1"}) as cliente:
        def ingresar(usuario):
            assert cliente.post("/api/sesion", json={"username": usuario,
                       "password": PASSWORD_PRUEBA}).status_code == 200

        ingresar("inf1")
        alta = cliente.post("/api/expedientes", json={
            "tipo": "servicio", "descripcion": "Mantenimiento de equipos informáticos",
            "fecha_requerimiento": date.today().isoformat(), "plazo_dias": 30,
            "monto": "1500.00", "entregables": [], "origen_entregables": "tdr"})
        assert alta.status_code == 201, alta.text
        expediente_id = alta.json()["id"]
        ruta = f"/api/expedientes/{expediente_id}"
        assert cliente.get(f"{ruta}/lecturas").json()["tdr"] == {
            "analizado": False, "pendientes": 0}
        assert cliente.post(f"{ruta}/tdr/observaciones", json={
            "detalle": "Precisar los equipos", "severidad": "bloqueante"}).status_code == 403

        ingresar("dec1")
        assert cliente.get(f"{ruta}/lecturas").status_code == 200
        assert cliente.post(f"{ruta}/tdr/observaciones", json={
            "detalle": "Precisar los equipos", "severidad": "bloqueante"}).status_code == 204
        observacion_id = cliente.get(f"{ruta}/lecturas").json()["observaciones"][0]["id"]
        assert cliente.post(f"{ruta}/tdr/observaciones/{observacion_id}/responder",
                            json={"estado": "justificada", "respuesta": "Anexo 1"}).status_code == 403

        ingresar("inf1")
        assert cliente.post(f"{ruta}/tdr/observaciones/{observacion_id}/responder",
                            json={"estado": "justificada", "respuesta": "Anexo 1"}).status_code == 204
        assert cliente.get(f"{ruta}/lecturas").json()["tdr"]["pendientes"] == 0
