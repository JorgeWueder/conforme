from conforme import repositorio
from scripts import caso_limpieza
from tests.conftest import actor_de


def test_caso_limpieza_es_idempotente_y_recorre_el_ciclo(sesion_sembrada):
    s = sesion_sembrada
    identificador = caso_limpieza.crear(s)
    assert identificador is not None
    assert caso_limpieza.crear(s) is None
    sg1, dec1 = actor_de(s, "sg1"), actor_de(s, "dec1")
    exp = repositorio.obtener_expediente(s, sg1, identificador)
    assert exp["numero_orden"] == "OS-SIM-2026-L01" and not exp["tiene_conformidad"]
    entregables = repositorio.listar_entregables(s, sg1, identificador)
    assert [e["numero"] for e in entregables] == [1, 2]
    repositorio.registrar_observacion_de_entrega(
        s, sg1, identificador, entregable_id=entregables[1]["id"], texto="Falta el sustento del ambiente B.")
    assert repositorio.obtener_expediente(s, dec1, identificador)["observaciones_sin_comunicar"] == 1
    s.rollback()
