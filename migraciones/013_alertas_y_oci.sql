-- Fase 1 (cimientos de la Fase 6): ámbito y carácter bloqueante de cada alerta, y
-- actuaciones de seguimiento del OCI, que nunca modifican decisiones de gestión.

ALTER TABLE alerta
    ADD COLUMN ambito TEXT NOT NULL DEFAULT 'operativa_tesoreria'
        CHECK (ambito IN ('operativa_tesoreria', 'preventiva_dec', 'seguimiento_oci')),
    ADD COLUMN bloqueante BOOLEAN NOT NULL DEFAULT false;

CREATE TABLE actuacion_oci (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entidad     TEXT NOT NULL CHECK (entidad IN ('expediente', 'revision_previa', 'conflicto_interes')),
    entidad_id  BIGINT NOT NULL,
    tipo        TEXT NOT NULL CHECK (tipo IN ('observacion_seguimiento', 'requerimiento_info',
                                              'recomendacion', 'alerta_seguimiento')),
    descripcion TEXT NOT NULL CHECK (length(btrim(descripcion)) > 0),
    autor_id    BIGINT NOT NULL REFERENCES persona (id),
    creado_en   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_actuacion_oci_entidad ON actuacion_oci (entidad, entidad_id);
