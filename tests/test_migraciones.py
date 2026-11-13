from sqlalchemy import inspect, text

from conforme import migraciones


def test_crea_las_tablas_de_f1(engine):
    tablas = set(inspect(engine).get_table_names())
    assert {"area", "persona", "usuario", "proveedor", "expediente",
            "bitacora", "anomalia_sembrada", "migracion_aplicada"} <= tablas


def test_aplicar_dos_veces_no_hace_nada(engine):
    assert migraciones.aplicar(engine) == []
    with engine.connect() as c:
        nombres = c.execute(text("SELECT nombre FROM migracion_aplicada")).scalars().all()
    assert len(nombres) == len(set(nombres)) >= 1
