"""Sello de conformidad: código, QR, verificación pública y detección de alteraciones.

Las pruebas con base alteran datos dentro de la transacción de la sesión, que se
revierte al terminar.
"""
import io
import re

import pytest
from PIL import Image
from sqlalchemy import text

from conforme import repositorio, sello
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
    ultimo = s.execute(text(
        "SELECT max(id) FROM bitacora WHERE expediente_id = :e "
        "AND accion IN ('conformidad.registrada', 'evidencia.adjuntada')"), {"e": exp["id"]}
    ).scalar_one()
    assert conformidad["sello_bitacora_id"] == ultimo
    r = repositorio.consultar_sello(s, conformidad["codigo_sello"])
    assert r["integra"] and r["expediente"] == exp["codigo"]
