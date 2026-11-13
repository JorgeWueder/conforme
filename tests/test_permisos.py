import pytest
from sqlalchemy import text

from conforme import auth, repositorio
from conforme.permisos import PermisoDenegado
from tests.conftest import PASSWORD_PRUEBA


def _actor(sesion, username):
    actor = auth.autenticar(sesion, username, PASSWORD_PRUEBA)
    assert actor is not None
    return actor


def test_login_rechaza_clave_incorrecta_y_usuario_inexistente(sesion_sembrada):
    assert auth.autenticar(sesion_sembrada, "inf1", "otra-clave") is None
    assert auth.autenticar(sesion_sembrada, "nadie", PASSWORD_PRUEBA) is None


def test_roles_asignados_por_area(sesion_sembrada):
    assert _actor(sesion_sembrada, "inf1").rol == "area_usuaria"
    assert _actor(sesion_sembrada, "tes1").rol == "tesoreria"
    assert _actor(sesion_sembrada, "oci1").rol == "auditor"


def test_area_usuaria_solo_ve_expedientes_de_su_area(sesion_sembrada):
    filas = repositorio.listar_expedientes(sesion_sembrada, _actor(sesion_sembrada, "inf1"))
    assert 0 < len(filas) < 300
    assert {f["area_sigla"] for f in filas} == {"INF"}


@pytest.mark.parametrize("username", ["tes1", "oci1"])
def test_tesoreria_y_auditor_ven_todos(sesion_sembrada, username):
    filas = repositorio.listar_expedientes(sesion_sembrada, _actor(sesion_sembrada, username))
    assert len(filas) == 300


def test_area_usuaria_no_accede_a_expediente_ajeno(sesion_sembrada):
    auditor = _actor(sesion_sembrada, "oci1")
    inf = _actor(sesion_sembrada, "inf1")
    ajeno = next(f for f in repositorio.listar_expedientes(sesion_sembrada, auditor)
                 if f["area_sigla"] != "INF")
    assert repositorio.obtener_expediente(sesion_sembrada, inf, ajeno["id"]) is None
    with pytest.raises(PermisoDenegado):
        repositorio.linea_de_tiempo(sesion_sembrada, inf, ajeno["id"])


def test_linea_de_tiempo_de_expediente_propio(sesion_sembrada):
    inf = _actor(sesion_sembrada, "inf1")
    propio = repositorio.listar_expedientes(sesion_sembrada, inf, texto="EXP-2026-0300")[0]
    eventos = repositorio.linea_de_tiempo(sesion_sembrada, inf, propio["id"])
    acciones = [e["accion"] for e in eventos]
    assert acciones[:3] == ["expediente.registrado", "orden.emitida", "conformidad.registrada"]
    assert acciones.count("evidencia.adjuntada") >= 2
    assert acciones[-3:] == ["alerta.generada"] * 3
    assert eventos[0]["actor"] and eventos[1]["documento_sha256"]
    assert eventos[-1]["actor"] is None  # las alertas las genera el sistema


@pytest.mark.parametrize("username", ["inf1", "tes1"])
def test_bitacora_completa_solo_para_auditor(sesion_sembrada, username):
    actor = _actor(sesion_sembrada, username)
    with pytest.raises(PermisoDenegado):
        repositorio.listar_bitacora(sesion_sembrada, actor)
    with pytest.raises(PermisoDenegado):
        repositorio.verificar_integridad(sesion_sembrada, actor)


def test_auditor_verifica_la_cadena_sembrada(sesion_sembrada):
    auditor = _actor(sesion_sembrada, "oci1")
    resultado = repositorio.verificar_integridad(sesion_sembrada, auditor)
    assert resultado.integra
    assert resultado.total == sesion_sembrada.execute(
        text("SELECT count(*) FROM bitacora")).scalar_one() > 2000
    assert len(repositorio.listar_bitacora(sesion_sembrada, auditor, limite=50)) == 50
