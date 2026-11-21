"""Contrato HTTP que utiliza el frontend de React."""
import json

from fastapi.testclient import TestClient

from app import app
from conforme import db
from tests.conftest import PASSWORD_PRUEBA


def test_escrituras_requieren_el_encabezado_del_cliente():
    with TestClient(app) as cliente:
        respuesta = cliente.post("/api/sesion", json={"username": "inf1", "password": "irrelevante"})
        assert respuesta.status_code == 403
        assert cliente.delete("/api/sesion", headers={"X-Conforme": "1"}).status_code == 204


def test_sesion_alcance_y_sello_publico(engine, base_sembrada, monkeypatch):
    monkeypatch.setattr(db, "_engine", engine)
    monkeypatch.setenv("BASE_URL", "https://conforme.example")
    with TestClient(app, headers={"X-Conforme": "1"}) as cliente, TestClient(app) as visitante:
        assert visitante.get("/api/expedientes").status_code == 401
        inicio = cliente.post("/api/sesion", json={"username": "inf1", "password": PASSWORD_PRUEBA})
        assert inicio.status_code == 200
        assert "HttpOnly" in inicio.headers["set-cookie"]
        assert inicio.json()["rol"] == "area_usuaria"
        assert cliente.get("/api/bitacora").status_code == 403
        assert cliente.get("/api/sesion").json()["username"] == "inf1"

        expediente = cliente.get("/api/expedientes", params={"texto": "EXP-2026-0300"}).json()[0]
        detalle = cliente.get(f"/api/expedientes/{expediente['id']}").json()
        codigo = detalle["conformidad"]["codigo_sello"]
        publico = visitante.get(f"/api/sellos/{codigo}")
        assert publico.status_code == 200
        assert publico.json()["integra"]
        assert "conformante_id" not in publico.json()
        assert any(
            evidencia["miniatura"]
            for item in publico.json()["entregables"] for evidencia in item["evidencias"]
        )
        imagen = cliente.get(f"/api/expedientes/{expediente['id']}/sello")
        assert imagen.headers["content-type"] == "image/png"
        assert imagen.content.startswith(b"\x89PNG")
        assert cliente.delete("/api/sesion").status_code == 204
        assert cliente.get("/api/sesion").status_code == 401


def test_penalidad_sugerida_coincide_con_la_regla_r2(engine, base_sembrada, monkeypatch):
    monkeypatch.setattr(db, "_engine", engine)
    with TestClient(app, headers={"X-Conforme": "1"}) as cliente, TestClient(app) as visitante:
        assert cliente.post("/api/sesion", json={"username": "inf1", "password": PASSWORD_PRUEBA}).status_code == 200
        expediente = cliente.get("/api/expedientes", params={"texto": "EXP-2026-0300"}).json()[0]
        ruta = f"/api/expedientes/{expediente['id']}/penalidad"
        # Caso estrella: 12 días de atraso, S/ 3,200.00 esperados, tope S/ 4,800.00 (alerta R2).
        atrasada = cliente.get(ruta, params={"entrega": "2026-09-29"}).json()
        assert atrasada["fecha_limite"] == "2026-09-17"
        assert atrasada["dias_atraso"] == 12
        assert atrasada["penalidad_esperada"] == "3200.00"
        assert atrasada["penalidad_tope"] == "4800.00"
        assert atrasada["plazo_maximo_conformidad"] == 7
        a_tiempo = cliente.get(ruta, params={"entrega": "2026-09-17"}).json()
        assert a_tiempo["dias_atraso"] == 0 and a_tiempo["penalidad_esperada"] == "0.00"
        assert visitante.get(ruta, params={"entrega": "2026-09-29"}).status_code == 401
        assert cliente.post("/api/sesion", json={"username": "rh1", "password": PASSWORD_PRUEBA}).status_code == 200
        assert cliente.get(ruta, params={"entrega": "2026-09-29"}).status_code == 404


def test_conformidad_multipart_con_asignacion_de_evidencia(engine, base_sembrada, monkeypatch):
    monkeypatch.setattr(db, "_engine", engine)
    with TestClient(app, headers={"X-Conforme": "1"}) as cliente:
        assert cliente.post("/api/sesion", json={"username": "inf1", "password": PASSWORD_PRUEBA}).status_code == 200
        expediente = cliente.get("/api/expedientes", params={"texto": "EXP-2026-0295"}).json()[0]
        ruta = f"/api/expedientes/{expediente['id']}"
        entregables = cliente.get(ruta).json()["entregables"]
        datos = {
            "fecha_conformidad": "2026-11-20",
            "fecha_entrega_real": "2026-11-20",
            "penalidad_aplicada": "0.00",
            "items": [
                {"entregable_id": item["id"], "cumplido": True, "cantidad_archivos": int(i == 0)}
                for i, item in enumerate(entregables)
            ],
        }
        pdf = b"%PDF-1.4\n%%EOF"
        assert cliente.post(f"{ruta}/conformidad", data={"datos": json.dumps(datos)}).status_code == 422
        respuesta = cliente.post(
            f"{ruta}/conformidad", data={"datos": json.dumps(datos)},
            files=[("archivos", ("acta.pdf", pdf, "application/pdf"))],
        )
        assert respuesta.status_code == 201, respuesta.json()
        entregables = cliente.get(ruta).json()["entregables"]
        evidencia = entregables[0]["evidencias"][0]
        assert all(not item["evidencias"] for item in entregables[1:])
        descarga = cliente.get(f"/api/evidencias/{evidencia['id']}?descarga=true")
        assert descarga.content == pdf
        assert "attachment" in descarga.headers["content-disposition"]
