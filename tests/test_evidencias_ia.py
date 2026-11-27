"""La comparación asistida debe devolver señales trazables y admitir fotos."""
import io

from PIL import Image
from reportlab.pdfgen import canvas

from conforme.ia import evidencias as revision


def test_pdf_y_foto_se_comparan_con_el_entregable(monkeypatch):
    salida = io.BytesIO()
    pdf = canvas.Canvas(salida)
    pdf.drawString(40, 750, "Informe de mantenimiento de equipos de laboratorio")
    pdf.save()
    foto = io.BytesIO()
    Image.new("RGB", (20, 20), "red").save(foto, format="PNG")
    contexto = {"codigo": "EXP-1", "descripcion": "Mantenimiento de equipos de laboratorio",
                "tdr": {"objeto": "Mantenimiento de equipos de laboratorio"},
                "entregables": [{"id": 1, "numero": 1, "descripcion": "Informe de mantenimiento",
                                 "criterio_evidencia": "Informe firmado y fotos"}]}
    items = [{"entregable_id": 1, "cumplido": True, "evidencias": [
        {"nombre_archivo": "informe.pdf", "mime": "application/pdf", "contenido": salida.getvalue()},
        {"nombre_archivo": "foto.png", "mime": "image/png", "contenido": foto.getvalue()}]}]

    def respuesta(partes, contexto_ia, esquema):
        assert contexto_ia["tarea"] == "verificar_evidencias"
        assert any("Informe de mantenimiento de equipos" in p.get("text", "") for p in partes)
        assert any(p["type"] == "file" and p["mediaType"] == "image/png" for p in partes)
        return {"revisiones": [{"entregable_id": 1, "estado": "incoherente",
                               "explicacion": "La foto muestra otra prestación distinta del mantenimiento."}]}

    monkeypatch.setattr(revision.eve, "solicitar", respuesta)
    resultado = revision.verificar(contexto, items)
    assert resultado["estado"] == "completada"
    assert any("otra prestación" in h for h in resultado["hallazgos"])


def test_falla_del_agente_pide_revision_humana(monkeypatch):
    def falla(*_args):
        raise revision.eve.EveNoDisponible()

    monkeypatch.setattr(revision.eve, "solicitar", falla)
    resultado = revision.verificar(
        {"codigo": "EXP-2", "descripcion": "Entrega de equipo", "entregables": [
            {"id": 2, "numero": 1, "descripcion": "Equipo instalado",
             "criterio_evidencia": "Fotografía del equipo instalado"}]},
        [{"entregable_id": 2, "cumplido": True,
          "evidencias": [{"nombre_archivo": "foto.png", "mime": "image/png", "contenido": b"imagen"}]}])
    assert resultado["estado"] == "no_disponible"
    assert any("Abastecimiento" in h for h in resultado["hallazgos"])
