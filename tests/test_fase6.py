"""Separación de competencias y actuaciones de seguimiento de la fase 6."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from conforme import bitacora, integridad, repositorio
from conforme.modelos import Alerta, RevisionPrevia
from conforme.permisos import PermisoDenegado
from tests.conftest import actor_de


def test_panel_y_actuacion_oci_no_alteran_bloqueos(sesion_sembrada):
    s = sesion_sembrada
    oci, tes = actor_de(s, "oci1"), actor_de(s, "tes1")
    with pytest.raises(PermisoDenegado):
        integridad.panel(s, tes)
    expediente = repositorio.listar_expedientes(s, oci)[0]
    antes = repositorio.verificar_pago(s, tes, expediente["id"])
    with pytest.raises(PermisoDenegado):
        integridad.registrar_actuacion(s, tes, entidad="expediente",
            entidad_id=expediente["id"], tipo="recomendacion",
            descripcion="Solicito verificar la documentación.")
    actuacion_id = integridad.registrar_actuacion(s, oci, entidad="expediente",
        entidad_id=expediente["id"], tipo="alerta_seguimiento",
        descripcion="Revisar el patrón de contratación de este expediente.")
    panel = integridad.panel(s, oci)
    assert panel["actuaciones"][0]["id"] == actuacion_id
    seguimiento = next(a for a in panel["seguimiento"] if a["expediente_id"] == expediente["id"])
    alerta = next(a for a in repositorio.listar_alertas(s, oci) if a["id"] == seguimiento["id"])
    assert alerta["ambito"] == "seguimiento_oci" and not alerta["bloqueante"]
    assert seguimiento["id"] not in {a["id"] for a in repositorio.listar_alertas(s, tes)}
    repositorio.cerrar_alerta(s, oci, seguimiento["id"], "Seguimiento concluido.")
    despues = repositorio.verificar_pago(s, tes, expediente["id"])
    assert despues["bloqueos"] == antes["bloqueos"]
    assert bitacora.verificar_cadena(s).integra


def test_alerta_preventiva_exige_revisor_dec_independiente(sesion_sembrada):
    s = sesion_sembrada
    dec1, dec2, oci, tes = (actor_de(s, u) for u in ("dec1", "dec2", "oci1", "tes1"))
    expedientes = repositorio.listar_expedientes(s, dec1)
    usados = set(s.scalars(select(RevisionPrevia.expediente_id).where(
        RevisionPrevia.expediente_id.isnot(None))))
    exp = next(e for e in expedientes if e["id"] not in usados)
    ahora = datetime.now(timezone.utc)
    s.add(RevisionPrevia(expediente_id=exp["id"], asignado_id=dec1.usuario_id,
                         evaluador_id=dec1.usuario_id, creado_en=ahora))
    alerta = Alerta(expediente_id=exp["id"], regla="R6", clave="fase6-prueba",
                    severidad="media", explicacion="Revisión preventiva independiente.",
                    datos={}, estado="abierta", ambito="preventiva_dec", bloqueante=False,
                    creada_en=ahora, actualizada_en=ahora)
    s.add(alerta)
    s.flush()
    vista_dec1 = next(a for a in repositorio.listar_alertas(s, dec1) if a["id"] == alerta.id)
    vista_dec2 = next(a for a in repositorio.listar_alertas(s, dec2) if a["id"] == alerta.id)
    assert not vista_dec1["puede_revisar"] and vista_dec2["puede_revisar"]
    assert any(a["id"] == alerta.id for a in repositorio.listar_alertas(s, tes))
    with pytest.raises(PermisoDenegado):
        repositorio.cerrar_alerta(s, dec1, alerta.id, "Me reviso a mí mismo.")
    with pytest.raises(PermisoDenegado):
        repositorio.cerrar_alerta(s, oci, alerta.id, "Lo cierro desde OCI.")
    repositorio.cerrar_alerta(s, dec2, alerta.id, "Análisis independiente completado.")
    assert alerta.estado == "cerrada"
