import io
from collections import Counter
from datetime import timedelta

from PIL import Image
from sqlalchemy import text

from conforme import normativa
from datos import caso_estrella, generador


def test_misma_semilla_mismos_datos():
    assert generador.generar() == generador.generar()


def test_otra_semilla_otros_datos():
    assert generador.generar(1)["expedientes"] != generador.generar(2)["expedientes"]


def test_conteos():
    c = generador.generar()
    assert len(c["areas"]) == 12
    assert len(c["personas"]) == 60
    assert len(c["usuarios"]) == 60
    assert len(c["proveedores"]) == 120
    assert len(c["expedientes"]) == 300
    assert len(c["entregables"]) == 901
    assert len(c["conformidades"]) == 246
    assert len(c["pagos"]) == 207
    # 2 por expediente + 1 por conformidad + 1 por evidencia + 1 por pago
    assert len(c["eventos"]) == 600 + 246 + _n_evidencias(c) + 207


def _n_evidencias(conjunto):
    return sum(len(i["evidencias"]) for c in conjunto["conformidades"] for i in c["items"])


def test_anomalias_sembradas_por_regla():
    c = generador.generar()
    por_regla = Counter(a["regla"] for a in c["anomalias"])
    # 5 por regla + R1, R2 y R4 del caso estrella
    assert por_regla == {"R1": 6, "R2": 6, "R3": 5, "R4": 6, "R5": 5}
    parejas = [(a["expediente_codigo"], a["regla"]) for a in c["anomalias"]]
    assert len(parejas) == len(set(parejas))
    assert sorted(r for cod, r in parejas if cod == caso_estrella.CODIGO) == ["R1", "R2", "R4"]


def test_todo_expediente_tiene_entregables_numerados_desde_1():
    c = generador.generar()
    numeros = {}
    for e in c["entregables"]:
        numeros.setdefault(e["expediente_codigo"], []).append(e["numero"])
    assert set(numeros) == {x["codigo"] for x in c["expedientes"]}
    assert all(ns == list(range(1, len(ns) + 1)) and len(ns) >= 2 for ns in numeros.values())


def test_las_evidencias_son_imagenes_validas_y_pequenas():
    c = generador.generar()
    evidencias = [e for conf in c["conformidades"] for i in conf["items"] for e in i["evidencias"]]
    assert len(evidencias) > 500
    assert all(e["tamano"] == len(e["contenido"]) < 2048 for e in evidencias)
    imagen = Image.open(io.BytesIO(evidencias[0]["contenido"]))
    imagen.load()
    assert imagen.size == (16, 12)


def test_identificadores_sinteticos_y_unicos():
    c = generador.generar()
    dnis = [p["dni"] for p in c["personas"]]
    rucs = [p["ruc"] for p in c["proveedores"]]
    assert all(len(d) == 8 and d.isdigit() and d.startswith("99") for d in dnis)
    assert all(len(r) == 11 and r.isdigit() and r.startswith("99") for r in rucs)
    for valores in (dnis, rucs, [x["codigo"] for x in c["expedientes"]],
                    [u["username"] for u in c["usuarios"]]):
        assert len(valores) == len(set(valores))


def test_solo_hay_atraso_donde_se_sembro_o_se_aplico_la_penalidad_completa():
    c = generador.generar()
    con_r2 = {a["expediente_codigo"] for a in c["anomalias"] if a["regla"] == "R2"}
    penalidad = {x["expediente_codigo"]: x["penalidad_aplicada"] for x in c["conformidades"]}
    atrasados, trampas = set(), 0
    for x in c["expedientes"]:
        if x["fecha_entrega_real"] is None:
            continue
        atraso = normativa.dias_de_atraso(x["fecha_orden"], x["plazo_dias"], x["fecha_entrega_real"])
        if atraso == 0:
            continue
        atrasados.add(x["codigo"])
        if x["codigo"] not in con_r2:  # caso trampa: no debe alertar
            trampas += 1
            assert penalidad[x["codigo"]] == normativa.penalidad_esperada(
                x["monto"], x["plazo_dias"], atraso)
    assert con_r2 <= atrasados
    assert trampas == 5


def test_caso_estrella_tiene_12_dias_de_atraso():
    x = next(e for e in generador.generar()["expedientes"] if e["codigo"] == caso_estrella.CODIGO)
    limite = x["fecha_orden"] + timedelta(days=x["plazo_dias"])
    assert (x["fecha_entrega_real"] - limite).days == 12
    assert x["tipo"] == "servicio"


def test_eventos_en_orden_cronologico():
    ts = [e["ts"] for e in generador.generar()["eventos"]]
    assert ts == sorted(ts)


def test_siembra_en_base(sesion_sembrada):
    contar = lambda tabla: sesion_sembrada.execute(text(f"SELECT count(*) FROM {tabla}")).scalar_one()
    assert contar("area") == 12
    assert contar("persona") == 60
    assert contar("usuario") == 60
    assert contar("proveedor") == 120
    assert contar("expediente") == 300
    c = generador.generar()
    assert contar("entregable") == 901
    assert contar("conformidad") == 246
    assert contar("conformidad_entregable") == sum(len(x["items"]) for x in c["conformidades"])
    assert contar("evidencia") == _n_evidencias(c)
    assert contar("pago") == 207
    assert contar("anomalia_sembrada") == 28
    assert contar("alerta") == 28
    assert contar("bitacora") == len(c["eventos"]) + 28  # + una "alerta.generada" por alerta
