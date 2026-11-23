"""R6 y R7 en el motor: miran expedientes distintos del que se evalúa."""
from datetime import date, timedelta

from sqlalchemy import text

from conforme import repositorio
from conforme.reglas import motor
from tests.conftest import actor_de

# Los datos sembrados llegan hasta fines de 2026: en 2027 no hay vecinos sembrados.
BASE = date(2027, 3, 1)


def _crear(s, inf1, proveedor_id, descripcion, orden):
    return repositorio.crear_expediente(
        s, inf1, tipo="servicio", descripcion=descripcion, proveedor_id=proveedor_id,
        numero_orden=f"OS-{orden:%Y%m%d}", fecha_requerimiento=orden - timedelta(days=3),
        fecha_orden=orden, fecha_inicio_prestacion=orden, plazo_dias=30, monto="12500.50",
        entregables=[{"numero": 1, "descripcion": "Informe final"}],
    )


def _alertas(s, actor, expediente_id, regla):
    return [a for a in repositorio.listar_alertas(s, actor, expediente_id=expediente_id)
            if a["regla"] == regla]


def test_los_datos_sembrados_terminan_antes_de_2027(sesion_sembrada):
    ultimo = sesion_sembrada.execute(text("SELECT max(fecha_orden) FROM expediente")).scalar_one()
    assert ultimo < BASE - timedelta(days=90)


def test_r6_se_genera_al_crear_el_tercer_expediente_del_proveedor(sesion_sembrada):
    s = sesion_sembrada
    inf1 = actor_de(s, "inf1")
    proveedor = repositorio.listar_proveedores(s, inf1)[10]["id"]
    a = _crear(s, inf1, proveedor, "Servicio A de prueba", BASE)
    b = _crear(s, inf1, proveedor, "Servicio B de prueba", BASE + timedelta(days=20))
    assert _alertas(s, inf1, a, "R6") == [] and _alertas(s, inf1, b, "R6") == []
    c = _crear(s, inf1, proveedor, "Servicio C de prueba", BASE + timedelta(days=45))
    [alerta] = _alertas(s, inf1, c, "R6")
    assert alerta["persona_implicada_id"] == inf1.persona_id and alerta["estado"] == "abierta"
    assert alerta["severidad"] == "media" and "3 expedientes" in alerta["explicacion"]
    # el expediente nuevo queda en ámbar y los anteriores no se alertan
    assert repositorio.obtener_expediente(s, inf1, c)["semaforo"] == "ambar"
    assert _alertas(s, inf1, a, "R6") == [] and _alertas(s, inf1, b, "R6") == []
    # y queda en la línea de tiempo del expediente
    assert "alerta.generada" in [e["accion"] for e in repositorio.linea_de_tiempo(s, inf1, c)]
    # reevaluar no duplica ni cambia nada
    tes1 = actor_de(s, "tes1")
    assert repositorio.reevaluar(s, tes1, c) == 0
    assert len(_alertas(s, inf1, c, "R6")) == 1


def test_r7_se_genera_al_repetir_la_prestacion_con_el_mismo_proveedor(sesion_sembrada):
    s = sesion_sembrada
    inf1 = actor_de(s, "inf1")
    proveedores = repositorio.listar_proveedores(s, inf1)
    proveedor, otro = proveedores[20]["id"], proveedores[21]["id"]
    desde = BASE + timedelta(days=300)
    primero = _crear(s, inf1, proveedor, "Servicio de fumigación de prueba", desde)
    otro_proveedor = _crear(s, inf1, otro, "Servicio de fumigación de prueba", desde + timedelta(days=5))
    otra_prestacion = _crear(s, inf1, proveedor, "Servicio de pintura de prueba", desde + timedelta(days=6))
    lejano = _crear(s, inf1, proveedor, "Servicio de fumigación de prueba", desde + timedelta(days=200))
    for exp in (primero, otro_proveedor, otra_prestacion, lejano):
        assert _alertas(s, inf1, exp, "R7") == []
    segundo = _crear(s, inf1, proveedor, "  servicio de FUMIGACIÓN de prueba ", desde + timedelta(days=30))
    [alerta] = _alertas(s, inf1, segundo, "R7")
    assert "2 veces" in alerta["explicacion"] and alerta["persona_implicada_id"] == inf1.persona_id


def test_sincronizar_solo_un_expediente_ve_a_los_anteriores_de_otros(sesion_sembrada):
    """Al reevaluar un expediente, sus vecinos se cargan aunque no se evalúen."""
    s = sesion_sembrada
    anterior = s.execute(text(
        "SELECT e.id FROM alerta a JOIN expediente e ON e.id = a.expediente_id "
        "WHERE a.regla = 'R6' ORDER BY e.id LIMIT 1")).scalar_one()
    fotos = {f.expediente_id: f for f in motor.cargar_fotos(s, [anterior])}
    assert len(fotos) == 1 and len(fotos[anterior].previos_mismo_proveedor) >= 2
    todas = {f.expediente_id: f for f in motor.cargar_fotos(s)}
    assert fotos[anterior].previos_mismo_proveedor == todas[anterior].previos_mismo_proveedor
    assert motor.sincronizar(s, [anterior]) == []  # ya existe: no se duplica


def test_cargar_fotos_de_ninguno_no_consulta_nada(sesion_sembrada):
    assert motor.cargar_fotos(sesion_sembrada, []) == []
    assert motor.sincronizar(sesion_sembrada, []) == []


def test_la_base_admite_las_reglas_r6_a_r8(sesion_sembrada):
    reglas = {f.regla for f in sesion_sembrada.execute(text("SELECT DISTINCT regla FROM alerta"))}
    assert {"R6", "R7", "R8"} <= reglas
