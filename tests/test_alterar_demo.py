"""alterar_demo: debe decir con claridad a qué base va a actuar."""
import pytest

from scripts import alterar_demo

DEMO = "postgresql://u:p@ep-round-cloud-1-pooler.c-16.aws.neon.tech/neondb?sslmode=require"
TEST = "postgresql://u:p@ep-noisy-truth-2-pooler.c-16.aws.neon.tech/neondb?sslmode=require"
DEV = "postgresql://u:p@ep-bold-lab-3.c-16.aws.neon.tech/neondb?sslmode=require"


def test_etiqueta_segun_el_servidor():
    assert alterar_demo.etiqueta_de_base(DEMO, DEMO, TEST) == "demo"
    assert alterar_demo.etiqueta_de_base(TEST, DEMO, TEST) == "test"
    assert alterar_demo.etiqueta_de_base(DEV, DEMO, TEST) == "dev"
    assert alterar_demo.etiqueta_de_base(DEV) == "dev"


def test_la_etiqueta_ignora_el_esquema_de_la_url_y_los_parametros():
    mismo_servidor = DEMO.replace("postgresql://", "postgres://").replace("?sslmode=require", "")
    assert alterar_demo.etiqueta_de_base(mismo_servidor, DEMO, TEST) == "demo"


def test_sin_terminal_ni_si_no_se_altera(monkeypatch, capsys):
    monkeypatch.setattr(alterar_demo.sys.stdin, "isatty", lambda: False)
    with pytest.raises(SystemExit, match="--si"):
        alterar_demo.confirmar("demo", "host/base", sin_preguntar=False)
    assert "DEMO" in capsys.readouterr().out  # aun así dice cuál era la base


def test_hay_que_escribir_el_nombre_de_la_base(monkeypatch):
    monkeypatch.setattr(alterar_demo.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "")
    with pytest.raises(SystemExit, match="Cancelado"):
        alterar_demo.confirmar("demo", "host/base", sin_preguntar=False)
    monkeypatch.setattr("builtins.input", lambda _: "dev")  # nombre equivocado
    with pytest.raises(SystemExit, match="Cancelado"):
        alterar_demo.confirmar("demo", "host/base", sin_preguntar=False)
    monkeypatch.setattr("builtins.input", lambda _: "demo")
    alterar_demo.confirmar("demo", "host/base", sin_preguntar=False)  # no falla


def test_con_si_no_pregunta(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("no debía preguntar"))
    alterar_demo.confirmar("demo", "host/base", sin_preguntar=True)
    assert "DEMO" in capsys.readouterr().out
