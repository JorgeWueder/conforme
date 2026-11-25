"""Motor de reglas sobre los datos sembrados: caso estrella, detección e idempotencia."""
from sqlalchemy import text

from conforme import bitacora, repositorio
from conforme.reglas import motor
from datos import caso_estrella
from scripts.medir_deteccion import medir
from tests.conftest import actor_de


def _contar(sesion, tabla):
    return sesion.execute(text(f"SELECT count(*) FROM {tabla}")).scalar_one()


def _estrella(sesion, actor):
    return repositorio.listar_expedientes(sesion, actor, texto=caso_estrella.CODIGO)[0]


def test_caso_estrella_muestra_r1_y_r2_antes_del_pago(sesion_sembrada):
    tes = actor_de(sesion_sembrada, "tes1")
    exp = _estrella(sesion_sembrada, tes)
    alertas = {a["regla"]: a for a in
               repositorio.listar_alertas(sesion_sembrada, tes, expediente_id=exp["id"])}
    assert sorted(alertas) == ["R1", "R2"]
    assert exp["semaforo"] == "rojo"
    assert (exp["alertas_altas"], exp["alertas_medias"]) == (1, 1)
    assert "n.º 3 «Informe final con registro fotográfico»" in alertas["R1"]["explicacion"]
    assert alertas["R2"]["datos"]["penalidad_esperada"] == "2880.00"
    inf1 = actor_de(sesion_sembrada, "inf1")
    assert {a["persona_implicada_id"] for a in alertas.values()} == {inf1.persona_id}
    assert {a["estado"] for a in alertas.values()} == {"abierta"}


def test_detecta_todas_las_anomalias_sembradas_sin_falsos_positivos(sesion_sembrada):
    m = medir(sesion_sembrada)
    assert m["sembradas"] == 41  # 39 repartidas + 2 del caso estrella
    assert m["no_detectadas"] == []
    assert m["falsos_positivos"] == []
    assert m["detectadas"] == m["alertas"] == 41
    assert m["por_regla"] == {"R1": (6, 6), "R2": (6, 6), "R3": (5, 5),
                              "R4": (5, 5), "R5": (5, 5), "R6": (4, 4),
                              "R7": (5, 5), "R8": (5, 5)}


def test_reevaluar_no_duplica(sesion_sembrada):
    alertas, registros = _contar(sesion_sembrada, "alerta"), _contar(sesion_sembrada, "bitacora")
    assert motor.sincronizar(sesion_sembrada) == []
    assert motor.sincronizar(sesion_sembrada) == []
    assert _contar(sesion_sembrada, "alerta") == alertas
    assert _contar(sesion_sembrada, "bitacora") == registros


def test_reevaluar_desde_el_repositorio(sesion_sembrada):
    tes = actor_de(sesion_sembrada, "tes1")
    assert repositorio.reevaluar(sesion_sembrada, tes, _estrella(sesion_sembrada, tes)["id"]) == 0


def test_una_alerta_cerrada_no_se_reabre_ni_se_duplica(sesion_sembrada):
    oci = actor_de(sesion_sembrada, "oci1")
    exp = _estrella(sesion_sembrada, oci)
    for a in repositorio.listar_alertas(sesion_sembrada, oci, expediente_id=exp["id"]):
        repositorio.cerrar_alerta(sesion_sembrada, oci, a["id"], "Revisado en la prueba.")
    assert motor.sincronizar(sesion_sembrada, [exp["id"]]) == []
    alertas = repositorio.listar_alertas(sesion_sembrada, oci, expediente_id=exp["id"])
    assert [a["estado"] for a in alertas] == ["cerrada"] * 2
    assert _estrella(sesion_sembrada, oci)["semaforo"] == "verde"


def test_la_cadena_sembrada_con_alertas_es_integra(sesion_sembrada):
    resultado = bitacora.verificar_cadena(sesion_sembrada)
    assert resultado.integra
    ts = [f.ts for f in sesion_sembrada.execute(text("SELECT ts FROM bitacora ORDER BY id"))]
    assert ts == sorted(ts)
