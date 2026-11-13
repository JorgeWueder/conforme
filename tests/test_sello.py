"""Sello de conformidad: código, QR, verificación pública y detección de alteraciones.

Las pruebas con base alteran datos dentro de la transacción de la sesión, que se
revierte al terminar.
"""
import io
import re
from datetime import timedelta

import pytest
from PIL import Image
from sqlalchemy import text

from conforme import config, repositorio, sello
from datos import caso_estrella
from tests.conftest import actor_de
from tests.test_conformidad import _pendiente, _registrar

BASE = "https://conforme.example.test"


# --- Sin base de datos ----------------------------------------------------------

def test_codigos_unicos_y_con_forma_valida():
    codigos = {sello.generar_codigo() for _ in range(2000)}
    assert len(codigos) == 2000
    assert all(sello.codigo_valido(c) for c in codigos)


@pytest.mark.parametrize("codigo", [None, "", "corto", "x" * 17, "con espacio 1234567",
                                    "'; DROP TABLE a;--", "../../etc/passwd!!"])
def test_codigo_con_forma_invalida(codigo):
    assert not sello.codigo_valido(codigo)


def test_url_de_verificacion():
    assert sello.url_verificacion("abc", BASE) == f"{BASE}/verificar?c=abc"
    assert sello.url_verificacion("abc", BASE + "/") == f"{BASE}/verificar?c=abc"


def test_el_qr_decodifica_a_la_url_esperada():
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    detector = cv2.QRCodeDetectorAruco()  # el detector clásico falla en ~1 % de QR válidos
    for _ in range(40):  # varios códigos: un QR mal formado fallaría en alguno
        codigo = sello.generar_codigo()
        for png in (sello.png_qr(codigo, BASE),
                    sello.png_sello(codigo, "EXP-2026-0001", "a" * 64, BASE)):
            imagen = Image.open(io.BytesIO(png)).convert("RGB")
            leido, _, _ = detector.detectAndDecode(np.array(imagen))
            assert leido == f"{BASE}/verificar?c={codigo}", codigo


def test_miniatura_solo_de_imagenes():
    imagen = io.BytesIO()
    Image.new("RGB", (800, 600), "red").save(imagen, format="PNG")
    mini = Image.open(io.BytesIO(sello.miniatura(imagen.getvalue())))
    assert max(mini.size) == sello.LADO_MINIATURA
    assert sello.miniatura(b"%PDF-1.4 no es una imagen") is None


def _entorno(monkeypatch, **valores):
    monkeypatch.setattr(config, "leer", lambda nombre, defecto=None: valores.get(nombre, defecto))


def test_sin_base_url_el_qr_usa_el_servidor_actual_y_solo_al_final_localhost(monkeypatch):
    _entorno(monkeypatch)
    assert sello.url_base("https://conforme-x.streamlit.app") == "https://conforme-x.streamlit.app"
    assert sello.url_base(None) == "http://localhost:8501"
    assert sello.aviso_url_base("https://conforme-x.streamlit.app") is None  # nada que avisar


def test_con_base_url_se_usa_esa_aunque_difiera(monkeypatch):
    _entorno(monkeypatch, BASE_URL="https://dominio.example/")
    assert sello.url_base("https://otro.streamlit.app") == "https://dominio.example"


def test_aviso_cuando_base_url_apunta_a_otro_servidor(monkeypatch):
    _entorno(monkeypatch, BASE_URL="https://conforme.streamlit.app")
    aviso = sello.aviso_url_base("https://conforme-gyc3.streamlit.app")
    assert aviso and "conforme.streamlit.app" in aviso and "conforme-gyc3" in aviso
    _entorno(monkeypatch, BASE_URL="http://localhost:8501")
    assert sello.aviso_url_base("https://conforme-gyc3.streamlit.app")  # localhost en el despliegue


def test_en_local_no_hay_aviso_aunque_cambie_el_puerto(monkeypatch):
    _entorno(monkeypatch, BASE_URL="http://localhost:8501")
    assert sello.aviso_url_base("http://localhost:8502") is None
    _entorno(monkeypatch, BASE_URL="https://app.example/")
    assert sello.aviso_url_base("https://APP.example:443") is None
    assert sello.aviso_url_base(None) is None


# --- Con base de datos ----------------------------------------------------------

def _estrella(s):
    inf1 = actor_de(s, "inf1")
    exp = next(x for x in repositorio.listar_expedientes(s, inf1)
               if x["codigo"] == caso_estrella.CODIGO)
    return exp, repositorio.obtener_conformidad(s, inf1, exp["id"])


def test_la_siembra_sella_todas_las_conformidades(sesion_sembrada):
    total, sellados, distintos = sesion_sembrada.execute(text(
        "SELECT count(*), count(codigo_sello), count(DISTINCT codigo_sello) FROM conformidad"
    )).one()
    assert total > 0 and total == sellados == distintos


def test_verificacion_publica_del_caso_estrella(sesion_sembrada):
    s = sesion_sembrada
    _, conformidad = _estrella(s)
    r = repositorio.consultar_sello(s, conformidad["codigo_sello"])
    assert r["integra"] and r["problemas"] == []
    assert r["expediente"] == caso_estrella.CODIGO
    assert r["registros_verificados"] > 0
    assert any(not e["evidencias"] for e in r["entregables"])  # el que no tiene evidencia
    assert any(ev["miniatura"] for e in r["entregables"] for ev in e["evidencias"])


def test_codigo_inexistente_o_malformado_no_revela_nada(sesion_sembrada):
    for codigo in (sello.generar_codigo(), "malformado", None, ""):
        assert repositorio.consultar_sello(sesion_sembrada, codigo) is None


def test_la_consulta_publica_no_expone_dni_ni_otros_expedientes(sesion_sembrada):
    s = sesion_sembrada
    _, conformidad = _estrella(s)
    r = repositorio.consultar_sello(s, conformidad["codigo_sello"])
    volcado = repr({k: v for k, v in r.items()
                    if k not in ("entregables",)}) + repr(
        [{k: v for k, v in e.items()} for e in r["entregables"]])
    dnis = s.execute(text("SELECT dni FROM persona")).scalars().all()
    assert not any(dni in volcado for dni in dnis)
    assert "dni" not in " ".join(r)
    assert set(re.findall(r"EXP-\d+-\d+", volcado)) == {caso_estrella.CODIGO}


def test_modificar_un_registro_de_bitacora_se_detecta(sesion_sembrada):
    s = sesion_sembrada
    _, conformidad = _estrella(s)
    registro = conformidad["sello_bitacora_id"]
    s.execute(text("UPDATE bitacora SET detalle = detalle || '{\"x\": 1}' WHERE id = :i"),
              {"i": registro})
    r = repositorio.consultar_sello(s, conformidad["codigo_sello"])
    assert not r["integra"]
    assert any(f"n.º {registro}" in p for p in r["problemas"])


def test_borrar_los_ultimos_registros_lo_detecta_el_sello(sesion_sembrada):
    """La cadena sola no ve el borrado de la cola; el sello sí."""
    s = sesion_sembrada
    _, conformidad = _estrella(s)
    s.execute(text("DELETE FROM bitacora WHERE id >= :i"), {"i": conformidad["sello_bitacora_id"]})
    r = repositorio.consultar_sello(s, conformidad["codigo_sello"])
    assert not r["integra"]
    assert any("falta o cambió" in p for p in r["problemas"])


def test_alterar_el_archivo_de_una_evidencia_se_detecta(sesion_sembrada):
    s = sesion_sembrada
    _, conformidad = _estrella(s)
    s.execute(text(
        "UPDATE evidencia SET contenido = '\\x00'::bytea WHERE id = ("
        " SELECT ev.id FROM evidencia ev JOIN conformidad_entregable ce"
        "  ON ce.id = ev.conformidad_entregable_id"
        " JOIN conformidad c ON c.id = ce.conformidad_id"
        " WHERE c.codigo_sello = :c ORDER BY ev.id LIMIT 1)"
    ), {"c": conformidad["codigo_sello"]})
    r = repositorio.consultar_sello(s, conformidad["codigo_sello"])
    assert not r["integra"]
    assert any("evidencia" in p for p in r["problemas"])


def test_una_conformidad_nueva_queda_sellada_e_integra(sesion_sembrada):
    s = sesion_sembrada
    inf2 = actor_de(s, "inf2")
    exp = _pendiente(s, inf2)
    _registrar(s, inf2, exp)
    conformidad = repositorio.obtener_conformidad(s, inf2, exp["id"])
    assert sello.codigo_valido(conformidad["codigo_sello"])
    sellada = s.execute(text(
        "SELECT id, hash, detalle FROM bitacora WHERE expediente_id = :e "
        "AND accion = 'conformidad.sellada'"), {"e": exp["id"]}).one()
    assert conformidad["sello_bitacora_id"] == sellada.id
    assert conformidad["sello_hash"] == sellada.hash
    assert set(sellada.detalle["secciones"]) == {"expediente", "conformidad", "entregables",
                                                 "evidencias"}
    r = repositorio.consultar_sello(s, conformidad["codigo_sello"])
    assert r["integra"] and r["expediente"] == exp["codigo"]


def test_el_codigo_del_sello_no_queda_en_la_bitacora(sesion_sembrada):
    s = sesion_sembrada
    codigos = s.execute(text("SELECT codigo_sello FROM conformidad")).scalars().all()
    volcado = " ".join(s.execute(text("SELECT detalle::text FROM bitacora")).scalars().all())
    assert not any(c in volcado for c in codigos)


def test_lo_que_ocurre_despues_del_sello_no_lo_invalida(sesion_sembrada):
    """Pagos, alertas y reevaluaciones son posteriores y no forman parte del contenido sellado."""
    s = sesion_sembrada
    exp, conformidad = _estrella(s)
    tes1, oci1 = actor_de(s, "tes1"), actor_de(s, "oci1")
    repositorio.registrar_pago(s, tes1, exp["id"], fecha_pago=exp["fecha_orden"] + timedelta(days=100),
                               monto="1000.00")
    repositorio.reevaluar(s, tes1, exp["id"])
    alerta = repositorio.listar_alertas(s, oci1, expediente_id=exp["id"])[0]
    repositorio.cerrar_alerta(s, oci1, alerta["id"], "Revisada")
    assert repositorio.consultar_sello(s, conformidad["codigo_sello"])["integra"]


# Cada manipulación hecha directamente en la base (sin pasar por la aplicación) debe detectarse.
_C = "(SELECT id FROM conformidad WHERE codigo_sello = :c)"
_CE3 = ("(SELECT ce.id FROM conformidad_entregable ce JOIN entregable e ON e.id = ce.entregable_id"
        f" WHERE ce.conformidad_id = {_C} AND e.numero = 3)")
MANIPULACIONES = {
    "penalidad": "UPDATE conformidad SET penalidad_aplicada = 3200 WHERE codigo_sello = :c",
    "fecha_conformidad":
        "UPDATE conformidad SET fecha_conformidad = fecha_conformidad + 10 WHERE codigo_sello = :c",
    "observaciones":
        "UPDATE conformidad SET observaciones = 'texto cambiado' WHERE codigo_sello = :c",
    "conformante": "UPDATE conformidad SET conformante_id = (SELECT max(id) FROM persona) "
                   "WHERE codigo_sello = :c",
    "entregable_no_cumplido":
        f"UPDATE conformidad_entregable SET cumplido = false WHERE id = {_CE3}",
    "observacion_de_entregable":
        f"UPDATE conformidad_entregable SET observacion = 'otra' WHERE id = {_CE3}",
    "descripcion_de_entregable":
        "UPDATE entregable SET descripcion = 'otra cosa' WHERE numero = 1 AND expediente_id = "
        f"(SELECT expediente_id FROM conformidad WHERE id = {_C})",
    "monto_del_expediente":
        f"UPDATE expediente SET monto = 1000 WHERE id = (SELECT expediente_id FROM conformidad"
        f" WHERE id = {_C})",
    "fecha_de_entrega":
        f"UPDATE expediente SET fecha_entrega_real = fecha_entrega_real - 20 WHERE id = ("
        f"SELECT expediente_id FROM conformidad WHERE id = {_C})",
    "borrar_una_evidencia":
        "DELETE FROM evidencia WHERE id = (SELECT ev.id FROM evidencia ev JOIN"
        " conformidad_entregable ce ON ce.id = ev.conformidad_entregable_id"
        f" WHERE ce.conformidad_id = {_C} ORDER BY ev.id LIMIT 1)",
    "evidencia_falsa_sin_bitacora":
        "INSERT INTO evidencia (conformidad_entregable_id, nombre_archivo, mime, tamano, sha256,"
        " contenido, subido_por, subido_en) SELECT ce.id, 'falsa.pdf', 'application/pdf', 4,"
        " repeat('a', 64), '\x25504446'::bytea, 1, now() FROM conformidad_entregable ce"
        f" WHERE ce.conformidad_id = {_C} LIMIT 1",
    "borrar_el_estado_de_un_entregable":
        f"DELETE FROM conformidad_entregable WHERE id = {_CE3}",
}


@pytest.mark.parametrize("nombre", sorted(MANIPULACIONES))
def test_manipular_los_datos_directamente_en_la_base_se_detecta(sesion_sembrada, nombre):
    s = sesion_sembrada
    _, conformidad = _estrella(s)
    antes = repositorio.consultar_sello(s, conformidad["codigo_sello"])
    assert antes["integra"]
    s.execute(text(MANIPULACIONES[nombre]), {"c": conformidad["codigo_sello"]})
    despues = repositorio.consultar_sello(s, conformidad["codigo_sello"])
    assert not despues["integra"], nombre
    assert despues["problemas"]
