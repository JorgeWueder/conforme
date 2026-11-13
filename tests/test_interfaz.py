"""md(): el texto de personas no puede convertirse en enlaces, imágenes ni formato."""
import re

import pytest

from conforme.interfaz import md


@pytest.mark.parametrize("entrada", [
    "[Pulsa aquí](http://evil.example/login)",
    "![pixel](http://evil.example/p.png)",
    "<img src=x onerror=alert(1)>",
    "**negrita** _cursiva_ `código` ~~tachado~~",
    ":red-badge[Cumplido] :material/warning:",
    "$$x^2$$ y $y$",
    "# titulo\n- lista\n> cita",
])
def test_ningun_caracter_especial_queda_sin_escapar(entrada):
    escapado = md(entrada)
    sin_escapes = re.sub(r"\\.", "", escapado)  # lo escapado deja de contar
    assert not re.search(r"[\`*_{}\[\]()<>#+!|~$:&]", sin_escapes), escapado
    assert "\n" not in escapado


def test_texto_normal_se_conserva_y_none_es_vacio():
    assert md("Informe final, 3 págs.") == "Informe final, 3 págs."
    assert md(None) == ""
    assert md("a   b\n\nc") == "a b c"


# --- Línea de tiempo --------------------------------------------------------------

from datetime import datetime, timezone  # noqa: E402

from conforme.interfaz import COLOR_ACCION, html_linea_de_tiempo  # noqa: E402


def _evento(i, accion="expediente.registrado", actor="Ana Pérez", resumen=None, doc=None,
            nombre="x.pdf"):
    return {"id": i, "ts": datetime(2026, 8, 19, 17, 22, tzinfo=timezone.utc), "accion": accion,
            "actor": actor, "detalle": {"resumen": resumen, "documento": nombre},
            "documento_sha256": doc}


def test_la_linea_de_tiempo_tiene_un_punto_por_evento_y_la_ultima_sin_linea():
    h = html_linea_de_tiempo([_evento(1), _evento(2, "orden.emitida"), _evento(3, "pago.registrado")])
    assert h.count("border-radius:50%") == 3
    assert h.count("border-left:2px solid transparent") == 1  # solo el último
    assert h.index("Expediente registrado") < h.index("Orden emitida") < h.index("Pago registrado")
    assert COLOR_ACCION["pago.registrado"] in h
    assert "19/08/2026" in h and "12:22" in h  # hora de Perú (UTC-5)
    assert "\n" not in h and "    " not in h     # nada que markdown tome por un bloque de código


def test_la_linea_de_tiempo_escapa_todo_dato_dinamico():
    malo = '<script>alert(1)</script><img src=x onerror=alert(2)>'
    h = html_linea_de_tiempo([_evento(7, actor=malo, resumen=malo, doc="a" * 64, nombre=malo)])
    assert "<script" not in h and "<img" not in h
    assert "&lt;script&gt;" in h
    assert "SHA-256" in h and "a" * 16 in h and "a" * 17 not in h


def test_accion_desconocida_y_sin_actor_no_rompen():
    h = html_linea_de_tiempo([_evento(1, accion="algo.nuevo", actor=None)])
    assert "algo.nuevo" in h and "Sistema" in h
    assert html_linea_de_tiempo([]) == '<div style="margin:4px 0 8px 0"></div>'
