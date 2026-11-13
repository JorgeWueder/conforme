from datetime import timedelta

from sqlalchemy import text

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
    assert len(c["eventos"]) == 600


def test_identificadores_sinteticos_y_unicos():
    c = generador.generar()
    dnis = [p["dni"] for p in c["personas"]]
    rucs = [p["ruc"] for p in c["proveedores"]]
    assert all(len(d) == 8 and d.isdigit() and d.startswith("99") for d in dnis)
    assert all(len(r) == 11 and r.isdigit() and r.startswith("99") for r in rucs)
    for valores in (dnis, rucs, [x["codigo"] for x in c["expedientes"]],
                    [u["username"] for u in c["usuarios"]]):
        assert len(valores) == len(set(valores))


def test_expedientes_generados_no_tienen_atraso_en_f1():
    for x in generador.generar()["expedientes"]:
        if x["codigo"] == caso_estrella.CODIGO or x["fecha_entrega_real"] is None:
            continue
        assert x["fecha_entrega_real"] <= x["fecha_orden"] + timedelta(days=x["plazo_dias"])


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
    assert contar("bitacora") == 600
