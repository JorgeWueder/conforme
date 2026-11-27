-- Habilita alerta interna (I1) y decisiones formales de Auditoría e Integridad.
ALTER TABLE alerta DROP CONSTRAINT alerta_regla_check;
ALTER TABLE alerta ADD CONSTRAINT alerta_regla_check
    CHECK (regla IN (
        'R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7', 'R8',
        'P1', 'P2', 'P3', 'P4',
        'D1', 'D2', 'D3',
        'I1',
        'OCI'
    ));

ALTER TABLE actuacion_oci DROP CONSTRAINT actuacion_oci_tipo_check;
ALTER TABLE actuacion_oci ADD CONSTRAINT actuacion_oci_tipo_check
    CHECK (tipo IN (
        'observacion_seguimiento', 'requerimiento_info', 'recomendacion', 'alerta_seguimiento',
        'recomendar_abstencion', 'derivar_sancion', 'solicitar_descargos', 'archivar_sustento'
    ));
