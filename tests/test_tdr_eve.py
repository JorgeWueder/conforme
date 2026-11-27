"""El TDR puede leerse con la sesión local de eve sin una clave API directa."""
from conforme.ia import eve, extractor


def test_lectura_tdr_usa_eve_y_comparacion_aislada(monkeypatch):
    tareas = []

    def respuesta(mensaje, contexto, esquema):
        tareas.append(contexto["tarea"])
        if contexto["tarea"] == "comparar_objetos":
            assert "Documento:" not in mensaje
            return {"corresponde": True, "motivo": ""}
        assert "DOCUMENTO:" in mensaje
        return {"objeto": "Mantenimiento de equipos de laboratorio",
                "corresponde_al_expediente": True, "motivo_discrepancia": "",
                "entregables": [{"numero": 1, "descripcion": "Informe técnico firmado"}],
                "plazo_dias": 10, "penalidades": []}

    monkeypatch.setattr(eve, "configurado", lambda: True)
    monkeypatch.setattr(eve, "solicitar", respuesta)
    resultado = extractor.extraer(extractor.PDF_EJEMPLO.read_bytes(), expediente={
        "tipo": "servicio", "descripcion": "Mantenimiento de equipos de laboratorio",
        "plazo_dias": 10})
    assert resultado.origen == "modelo"
    assert resultado.propuesta.corresponde_al_expediente is True
    assert tareas == ["leer_tdr", "comparar_objetos"]
