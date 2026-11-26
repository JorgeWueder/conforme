"""Regresiones de permisos, concurrencia, fuentes y citas de Prevención."""
from datetime import date, timedelta
from time import monotonic
from zipfile import ZipFile
import json

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import app
from conforme import db
from conforme.prevencion import demo, investigador, simulador
from conforme.prevencion.esquemas import ruc_valido
from conforme.prevencion.ingesta import publicar
from tests.conftest import PASSWORD_PRUEBA

CANDIDATO = "20999999990"
ENTIDAD = "20999999981"


def _ingresar(cliente, usuario):
    respuesta = cliente.post("/api/sesion", json={"username": usuario, "password": PASSWORD_PRUEBA})
    assert respuesta.status_code == 200


def _actuar(cliente, ruta, ficha, **datos):
    respuesta = cliente.post(ruta, json={"version": ficha["version"], **datos})
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def test_revision_demo_cierre_permisos_y_version(engine, base_sembrada, monkeypatch):
    monkeypatch.setattr(db, "_engine", engine)
    monkeypatch.setenv("PREVENCION_DEMO", "1")
    monkeypatch.delenv("CONFORME_EVE_URL", raising=False)
    with TestClient(app, headers={"X-Conforme": "1"}) as cliente:
        assert cliente.get("/api/prevencion").status_code == 401
        _ingresar(cliente, "inf1")
        assert cliente.get("/api/prevencion").status_code == 403
        assert cliente.post("/api/prevencion/demo").status_code == 403
        _ingresar(cliente, "dec1")
        respuesta = cliente.post("/api/prevencion/demo")
        assert respuesta.status_code == 201
        inicial = respuesta.json()
        ruta = f"/api/prevencion/{inicial['id']}"
        assert cliente.get("/api/prevencion").json()["revisiones"][0]["id"] == inicial["id"]
        siguiente = _actuar(cliente, f"{ruta}/evaluacion", inicial)
        assert {h["ruc"] for h in siguiente["hallazgos"]} == {None, "99000000001", "99000000002", "99000000003"}
        assert cliente.post(f"{ruta}/evaluacion", json={"version": inicial["version"]}).status_code == 409
        assert cliente.post(f"{ruta}/cierre", json={"version": siguiente["version"], "nota": "Sin comprobar"}).status_code == 422

        siguiente = _actuar(cliente, f"{ruta}/investigaciones", siguiente, ruc="99000000001", acto="TCP-DEMO-017")
        borrador = siguiente["investigaciones"][0]
        assert len(borrador["afirmaciones"]) == 2
        assert borrador["modo"] == "ejemplo"

        for control in siguiente["controles"]:
            if control["obligatorio"]:
                siguiente = _actuar(cliente, f"{ruta}/constancias", siguiente, control=control["id"],
                                     resultado="verificado", referencia="ACTA-DEMO", nota="Revisión documentada.")
        for hallazgo in siguiente["hallazgos"]:
            if hallazgo["prioridad"] == "verificar":
                siguiente = _actuar(cliente, f"{ruta}/hallazgos", siguiente, hallazgo=hallazgo["id"],
                                     resultado="derivado", referencia="ACTA-DEMO", nota="Derivado a revisión independiente.")
        siguiente = _actuar(cliente, f"{ruta}/cierre", siguiente, nota="Se registraron las comprobaciones del ejemplo.")
        assert siguiente["estado"] == "cerrada"
        assert cliente.post(f"{ruta}/evaluacion", json={"version": siguiente["version"]}).status_code == 422


def test_publicar_cruzar_fuentes_y_descartar_posteriores(engine, base_sembrada, monkeypatch, tmp_path):
    monkeypatch.setattr(db, "_engine", engine)
    assert ruc_valido(CANDIDATO) and ruc_valido(ENTIDAD)
    corte = date.today() - timedelta(days=2)
    sanciones = tmp_path / "tcp.csv"
    sanciones.write_text(
        "FECHA_CORTE|RUC|NOMBRE_RAZONODENOMINACIONSOCIAL|NUMERO_RESOLUCION|FECHA_INICIO|FECHA_FIN\n"
        f"{corte}|{CANDIDATO}|Compañía de prueba|RES-PRUEBA|{corte}|\n",
        encoding="cp1252",
    )
    sunat = tmp_path / "padron.zip"
    with ZipFile(sunat, "w") as archivo:
        archivo.writestr("PADRON.txt", f"RUC|NOMBRE|ESTADO|CONDICION|\n{CANDIDATO}|Proveedor de prueba|ACTIVO|HABIDO|\n")
    ordenes = tmp_path / "ordenes.csv"
    ordenes.write_text(
        "RUC_PROVEEDOR|RUC_ENTIDAD|NUMERO_ORDEN|FECHA_ORDEN|OBJETO\n"
        f"{CANDIDATO}|{ENTIDAD}|OS-1|{corte}|Limpieza de ambientes\n"
        f"{CANDIDATO}|{ENTIDAD}|OS-2|{corte}|Limpieza de ambientes\n",
        encoding="utf-8",
    )
    origen = "https://www.gob.pe/689"
    with Session(engine) as sesion, sesion.begin():
        edicion, total = publicar(sesion, sanciones, "tcp", None, "Prueba", origen)
        assert total == 1
        assert publicar(sesion, sanciones, "tcp", None, "Prueba", origen) == (edicion, None)
        assert publicar(sesion, sunat, "sunat", corte, "Prueba", origen)[1] == 1
        assert publicar(sesion, ordenes, "orden", corte, "Prueba", origen)[1] == 2

    compra = {
        "requerimiento": "REQ-PRUEBA", "objeto": "Limpieza de ambientes", "entidad_ruc": ENTIDAD,
        "unidad": "Unidad", "rubro": "Limpieza", "modalidad": "Contrato menor", "importe": "500.0",
        "fecha": date.today().isoformat(), "candidatos": [{"ruc": CANDIDATO, "nombre": "Proveedor de prueba"}],
    }
    with TestClient(app, headers={"X-Conforme": "1"}) as cliente:
        _ingresar(cliente, "dec1")
        respuesta = cliente.post("/api/prevencion", json=compra)
        assert respuesta.status_code == 201, respuesta.text
        ficha = respuesta.json()
        ruta = f"/api/prevencion/{ficha['id']}"
        ficha = _actuar(cliente, f"{ruta}/evaluacion", ficha)
        assert {h["frente"] for h in ficha["hallazgos"]} == {"F03", "F04", "F08"}
        sancion = next(h for h in ficha["hallazgos"] if h["frente"] == "F03")
        assert sancion["evidencias"][0]["acto"] == "RES-PRUEBA"
        assert sancion["evidencias"][0]["fila"] == 2

        respuesta = cliente.put(ruta, json={
            "version": ficha["version"], "compra": {**compra, "fecha": str(corte - timedelta(days=1))},
        })
        assert respuesta.status_code == 200
        anterior = _actuar(cliente, f"{ruta}/evaluacion", respuesta.json())
        assert not anterior["hallazgos"]
        assert all(f["estado"] == "sin_edicion" for f in anterior["fuentes"])



def test_citas_exigen_documento_pagina_y_extracto_y_acotan_identidad():
    cita = {
        "afirmacion": "El documento reporta la aplicación de una medida.",
        "documento": "resolucion", "pagina": 2, "estado": "corroborado",
        "extracto": "La resolución aplica una medida temporal.",
    }
    borrador = investigador.Borrador.model_validate({
        "afirmaciones": [cita, {**cita, "pagina": 3}], "pendientes": [],
    })
    evidencia = [{"id": "resolucion", "titulo": "Resolución", "url": "https://www.gob.pe/689",
                  "paginas": [{"numero": 2, "texto": cita["extracto"]}]}]
    afirmaciones, pendientes = investigador.validar_citas(borrador, evidencia, CANDIDATO, None)
    assert [a["estado"] for a in afirmaciones] == ["por_verificar"]
    assert pendientes
    assert not investigador.url_oficial("https://ejemplo.com/?url=gob.pe")
    assert not investigador.url_oficial("http://www.gob.pe")


def test_eve_entrega_el_resultado_en_lotes_de_eventos():
    datos = dict(afirmaciones=[], pendientes=["Corroborar en el portal."])
    lotes = [
        {"$eve": "heartbeat"},
        {"facts": [{"type": "content.completed", "data": {"kind": "result", "value": datos}}]},
        {"facts": [
            {"type": "turn.settled", "data": {"outcome": "completed"}},
            {"type": "delivery.settled", "data": {"deliveryId": "entrega", "outcome": "handled"}},
        ]},
    ]
    respuesta = investigador._resultado_eve(map(json.dumps, lotes), "entrega", monotonic() + 1)
    assert respuesta.model_dump() == datos


def test_simulador_plan_analisis_demo_y_personalizado():
    compra_demo = demo.compra_demo().model_dump(mode="json")
    plan_demo = simulador.plan_analisis(compra_demo, es_demo=True)
    assert len(plan_demo["proveedores"]) == 3
    assert plan_demo["total_pasos"] == 3 * 6 + 2
    hallazgos_demo = [h for p in plan_demo["proveedores"] for h in p["hallazgos"]] + plan_demo["hallazgos_compra"]
    assert {h["ruc"] for h in hallazgos_demo} == {None, "99000000001", "99000000002", "99000000003"}

    compra_custom = {
        "requerimiento": "REQ-2026-099",
        "objeto": "Mantenimiento de laboratorios de computo",
        "entidad_ruc": ENTIDAD,
        "unidad": "Servicios Generales",
        "rubro": "Mantenimiento",
        "modalidad": "Contrato menor",
        "fecha": date.today().isoformat(),
        "importe": "12000.00",
        "moneda": "PEN",
        "tdr": "TDR-099",
        "candidatos": [
            {"ruc": CANDIDATO, "nombre": "Servicios Alfa SAC", "proforma": "COT-1", "importe": "12000.00"},
            {"ruc": ENTIDAD, "nombre": "Inversiones Beta EIRL", "proforma": "COT-2", "importe": "12000.00"},
        ],
        "intervinientes": [
            {"rol": "Comprador", "designacion": "Ana Perez", "referencia": "MEM-10"},
        ],
    }
    plan_completo = simulador.plan_analisis(compra_custom, es_demo=False)
    assert len(plan_completo["proveedores"]) == 2
    assert plan_completo["proveedores"][0]["nivel"] == "verificar"
    assert plan_completo["proveedores"][1]["nivel"] == "limpio"
    assert any(h["frente"] == "F09" for h in plan_completo["hallazgos_compra"])

    plan_unico = simulador.plan_analisis(compra_custom, es_demo=False, ruc=CANDIDATO)
    assert len(plan_unico["proveedores"]) == 1
    assert plan_unico["proveedores"][0]["ruc"] == CANDIDATO
    assert plan_unico["proveedores"][0]["nivel"] == plan_completo["proveedores"][0]["nivel"]
    assert not plan_unico["pasos_compra"]


def test_investigador_simulado_sin_eve(monkeypatch):
    monkeypatch.delenv("CONFORME_EVE_URL", raising=False)
    resultado = investigador.investigar(
        CANDIDATO, "RES-SIM-0210-2026-TCE", date.today().isoformat(), [],
        sintetico=False, simulado=True, nombre="Servicios Alfa SAC", operacion="op-test",
    )
    assert resultado["modo"] == "simulacion"
    assert len(resultado["afirmaciones"]) == 2
    assert resultado["pendientes"]


def test_analizar_streaming_ndjson_por_proveedor_y_completo(engine, base_sembrada, monkeypatch):
    monkeypatch.setattr(db, "_engine", engine)
    monkeypatch.setenv("PREVENCION_PAUSA_MS", "0")
    monkeypatch.delenv("CONFORME_EVE_URL", raising=False)
    compra = {
        "requerimiento": "REQ-STREAM-01",
        "objeto": "Suministro de insumos para laboratorio",
        "entidad_ruc": ENTIDAD,
        "unidad": "Laboratorios",
        "rubro": "Insumos",
        "modalidad": "Contrato menor",
        "importe": "9500.00",
        "fecha": date.today().isoformat(),
        "candidatos": [
            {"ruc": CANDIDATO, "nombre": "Distribuidora Norte SAC", "proforma": "COT-A", "importe": "9400.00"},
            {"ruc": ENTIDAD, "nombre": "Comercial Trujillo EIRL", "proforma": "COT-B", "importe": "9500.00"},
        ],
        "intervinientes": [{"rol": "Comprador", "designacion": "Luis Rios", "referencia": "MEM-22"}],
    }
    with TestClient(app, headers={"X-Conforme": "1"}) as cliente:
        _ingresar(cliente, "dec1")
        ficha = cliente.post("/api/prevencion", json=compra).json()
        ruta = f"/api/prevencion/{ficha['id']}"

        # RUC ajeno falla antes de abrir el stream
        assert cliente.post(f"{ruta}/analizar", json={"version": ficha["version"], "ruc": "20100000001"}).status_code == 422

        # Analisis de un solo proveedor en streaming NDJSON
        resp_uno = cliente.post(f"{ruta}/analizar", json={"version": ficha["version"], "ruc": CANDIDATO})
        assert resp_uno.status_code == 200
        assert "application/x-ndjson" in resp_uno.headers["content-type"]
        eventos_uno = [json.loads(linea) for linea in resp_uno.text.strip().splitlines()]
        assert eventos_uno[0]["tipo"] == "inicio"
        assert eventos_uno[-1]["tipo"] == "completado"
        ficha = eventos_uno[-1]["revision"]
        assert CANDIDATO in ficha["analisis"]
        assert ENTIDAD not in ficha["analisis"]
        assert len(ficha["analisis"][CANDIDATO]["verificaciones"]) == 6

        # Version anterior rechazada con 409
        assert cliente.post(f"{ruta}/analizar", json={"version": 1}).status_code == 409

        # Analisis completo de todos los proveedores y la compra
        resp_todos = cliente.post(f"{ruta}/analizar", json={"version": ficha["version"]})
        assert resp_todos.status_code == 200
        eventos_todos = [json.loads(linea) for linea in resp_todos.text.strip().splitlines()]
        tipos = [e["tipo"] for e in eventos_todos]
        assert "proveedor_inicio" in tipos and "paso_resultado" in tipos and "compra_inicio" in tipos
        ficha = eventos_todos[-1]["revision"]
        assert {CANDIDATO, ENTIDAD, "__compra__"} <= set(ficha["analisis"].keys())

        # Investigacion documental simulada funciona sin eve configurado
        ficha = _actuar(cliente, f"{ruta}/investigaciones", ficha, ruc=CANDIDATO)
        assert ficha["investigaciones"][0]["modo"] == "simulacion"

