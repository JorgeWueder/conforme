"""Fase 5: evidencia, reemisión y seis controles antes del pago."""
from dataclasses import replace
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from conforme import repositorio
from conforme.errores import ErrorValidacion
from conforme.modelos import Entregable, Evidencia, Expediente, Pago, VerificacionPago
from conforme.proveedores import repositorio as evaluacion
from scripts import casos_evaluacion
from tests.conftest import actor_de


def _preparar(sesion, fecha_orden=None):
    casos = casos_evaluacion.sembrar_casos(sesion)
    codigo = next(c for c, estado in casos if estado == "selección aprobada")
    expediente_id = sesion.scalar(select(Expediente.id).where(Expediente.codigo == codigo))
    area, dec, tes = (actor_de(sesion, usuario) for usuario in ("inf1", "dec1", "tes1"))
    evaluacion.confirmar_orden(
        sesion, area, expediente_id, numero_orden="OS-FASE5-001",
        fecha_orden=fecha_orden or date.today())
    return expediente_id, area, dec, tes


def _conformidad(sesion, area, expediente_id, *, evidencia=True,
                sustento_penalidad="", tipo_sustento_penalidad=None,
                referencia_sustento_penalidad="", items=None, verificacion_ia=None):
    items = items or [{"entregable_id": e["id"], "cumplido": True, "observacion": "",
              "evidencias": ([{"nombre_archivo": f"acta-{e['numero']}.pdf",
                               "mime": "application/pdf",
                               "contenido": f"%PDF-1.4 evidencia {e['numero']}".encode()}]
                             if evidencia else [])}
             for e in repositorio.listar_entregables(sesion, area, expediente_id)]
    return repositorio.registrar_conformidad(
        sesion, area, expediente_id, fecha_entrega_real=date.today(),
        fecha_conformidad=date.today(), penalidad_aplicada="0", items=items,
        sustento_penalidad=sustento_penalidad,
        tipo_sustento_penalidad=tipo_sustento_penalidad,
        referencia_sustento_penalidad=referencia_sustento_penalidad,
        verificacion_ia=verificacion_ia)


def test_criterio_generico_no_se_acepta(sesion_sembrada):
    sesion = sesion_sembrada
    casos = casos_evaluacion.sembrar_casos(sesion)
    codigo = next(c for c, estado in casos if estado == "selección aprobada")
    expediente_id = sesion.scalar(select(Expediente.id).where(Expediente.codigo == codigo))
    area = actor_de(sesion, "inf1")
    entregables = list(sesion.scalars(select(Entregable).where(
        Entregable.expediente_id == expediente_id).order_by(Entregable.numero)))
    criterios = [{"entregable_id": e.id, "criterio_evidencia": "archivo" if e == entregables[0]
                  else "Informe técnico firmado y acta de recepción"} for e in entregables]
    with pytest.raises(ErrorValidacion, match="Precisa la evidencia"):
        repositorio.definir_criterios_evidencia(sesion, area, expediente_id, criterios)


def test_pago_bloqueado_hasta_revision_favorable(sesion_sembrada):
    sesion = sesion_sembrada
    expediente_id, area, dec, tes = _preparar(sesion)
    control = repositorio.verificar_pago(sesion, tes, expediente_id)
    assert len(control["controles"]) == 6 and not control["apto"]
    assert control["controles"][0]["correcto"]
    with pytest.raises(ErrorValidacion, match="adjunta su evidencia"):
        _conformidad(sesion, area, expediente_id, evidencia=False)
    _conformidad(sesion, area, expediente_id)
    assert not repositorio.verificar_pago(sesion, tes, expediente_id)["apto"]
    with pytest.raises(ErrorValidacion, match="Pago bloqueado"):
        repositorio.registrar_pago(sesion, tes, expediente_id,
                                  fecha_pago=date.today(), monto="6500")
    repositorio.revisar_conformidad(
        sesion, dec, expediente_id, favorable=True, motivo="Evidencias revisadas.",
        referencia_derivacion="SIM-DER-F5")
    control = repositorio.verificar_pago(sesion, tes, expediente_id)
    assert control["apto"], control["bloqueos"]
    pago_id = repositorio.registrar_pago(sesion, tes, expediente_id,
                                        fecha_pago=date.today(), monto="6500")
    pago = sesion.get(Pago, pago_id)
    verificacion = sesion.get(VerificacionPago, pago.verificacion_pago_id)
    assert verificacion.apto_para_pago and len(verificacion.checklist["controles"]) == 6


def test_devolucion_permite_v2_y_conserva_sello_v1(sesion_sembrada):
    sesion = sesion_sembrada
    expediente_id, area, dec, tes = _preparar(sesion)
    _conformidad(sesion, area, expediente_id)
    primera = repositorio.obtener_conformidad(sesion, area, expediente_id)
    sello_v1 = primera["codigo_sello"]
    repositorio.revisar_conformidad(
        sesion, dec, expediente_id, favorable=False, motivo="Falta precisar la recepción.")
    assert not repositorio.verificar_pago(sesion, tes, expediente_id)["apto"]
    _conformidad(sesion, area, expediente_id)
    segunda = repositorio.obtener_conformidad(sesion, area, expediente_id)
    assert segunda["version"] == 2 and segunda["estado_revision_dec"] == "pendiente"
    historial = repositorio.historial_conformidades(sesion, area, expediente_id)
    assert [c["vigente"] for c in historial] == [False, True]
    assert repositorio.consultar_sello(sesion, sello_v1)["integra"]
    assert repositorio.consultar_sello(sesion, segunda["codigo_sello"])["integra"]
    assert len(repositorio.listar_entregables(sesion, area, expediente_id)) == 2


def test_penalidad_menor_a_la_estimada_exige_sustento(sesion_sembrada):
    sesion = sesion_sembrada
    expediente_id, area, _, _ = _preparar(sesion, fecha_orden=date.today() - timedelta(days=11))
    with pytest.raises(ErrorValidacion, match="Indica si hubo"):
        _conformidad(sesion, area, expediente_id)
    with pytest.raises(ErrorValidacion, match="Indica si hubo"):
        _conformidad(sesion, area, expediente_id,
                    sustento_penalidad="Se aprobó ampliación del plazo mediante informe formal.")
    with pytest.raises(ErrorValidacion, match="referencia"):
        _conformidad(sesion, area, expediente_id,
                    tipo_sustento_penalidad="ampliacion",
                    sustento_penalidad="Se aprobó ampliación del plazo mediante informe formal.")
    _conformidad(sesion, area, expediente_id,
                sustento_penalidad="Se aprobó ampliación del plazo mediante informe formal.",
                tipo_sustento_penalidad="ampliacion",
                referencia_sustento_penalidad="SIM-AMPL-001")
    assert "SIM-AMPL-001" in repositorio.obtener_conformidad(sesion, area, expediente_id)["sustento_penalidad"]


def test_archivo_reciclado_se_advierte_a_abastecimiento(sesion_sembrada):
    sesion = sesion_sembrada
    expediente_id, area, dec, _ = _preparar(sesion)
    reciclada = sesion.scalar(select(Evidencia))
    assert reciclada is not None
    items = [{"entregable_id": e["id"], "cumplido": True, "observacion": "",
              "evidencias": [{"nombre_archivo": reciclada.nombre_archivo if e["numero"] == 1 else "nuevo.pdf",
                             "mime": reciclada.mime if e["numero"] == 1 else "application/pdf",
                             "contenido": bytes(reciclada.contenido) if e["numero"] == 1
                             else b"%PDF-1.4 nuevo"}]}
             for e in repositorio.listar_entregables(sesion, area, expediente_id)]
    _conformidad(sesion, area, expediente_id, items=items)
    conformidad = repositorio.obtener_conformidad(sesion, area, expediente_id)
    assert any("otro expediente" in h for h in conformidad["verificacion_evidencias"]["hallazgos"])
    with pytest.raises(ErrorValidacion, match="señales"):
        repositorio.revisar_conformidad(
            sesion, dec, expediente_id, favorable=True, motivo="Revisado.",
            referencia_derivacion="SIM-DER-002")
    repositorio.revisar_conformidad(
        sesion, dec, expediente_id, favorable=True, motivo="El documento es legítimo.",
        referencia_derivacion="SIM-DER-002", advertencias_revisadas=True)


def test_incoherencia_ia_requiere_revision_expresa_de_dec(sesion_sembrada):
    sesion = sesion_sembrada
    expediente_id, area, dec, tes = _preparar(sesion)
    _conformidad(sesion, area, expediente_id, verificacion_ia={
        "estado": "completada", "revisiones": [],
        "hallazgos": ["Entregable 1: el informe describe otro servicio."]})
    conformidad = repositorio.obtener_conformidad(sesion, area, expediente_id)
    assert "otro servicio" in conformidad["verificacion_evidencias"]["hallazgos"][0]
    with pytest.raises(ErrorValidacion, match="señales"):
        repositorio.revisar_conformidad(sesion, dec, expediente_id, favorable=True,
                                       motivo="Revisado.", referencia_derivacion="SIM-DER-IA")
    assert not repositorio.verificar_pago(sesion, tes, expediente_id)["apto"]
    repositorio.revisar_conformidad(sesion, dec, expediente_id, favorable=False,
                                   motivo="La evidencia corresponde a otra prestación.")
    assert not repositorio.verificar_pago(sesion, tes, expediente_id)["apto"]


def test_misma_persona_no_puede_emitir_conformidad_y_registrar_pago(sesion_sembrada):
    sesion = sesion_sembrada
    expediente_id, area, dec, tes = _preparar(sesion)
    _conformidad(sesion, area, expediente_id)
    repositorio.revisar_conformidad(sesion, dec, expediente_id, favorable=True,
                                   motivo="Evidencias revisadas.",
                                   referencia_derivacion="SIM-DER-SEG")
    tes_misma_persona = replace(tes, persona_id=area.persona_id)
    control = repositorio.verificar_pago(sesion, tes_misma_persona, expediente_id)
    assert not control["controles"][5]["correcto"]
    with pytest.raises(ErrorValidacion, match="Pago bloqueado"):
        repositorio.registrar_pago(sesion, tes_misma_persona, expediente_id,
                                  fecha_pago=date.today(), monto="6500")
