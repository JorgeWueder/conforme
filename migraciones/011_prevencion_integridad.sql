-- Fase 1: la evaluación de proveedores de un expediente y la revisión independiente
-- (cuatro ojos). Quien evalúa no puede ser quien revisa: lo impide la propia base.

ALTER TABLE revision_previa
    ADD COLUMN expediente_id                     BIGINT REFERENCES expediente (id),
    ADD COLUMN evaluador_id                      BIGINT REFERENCES usuario (id),
    ADD COLUMN revisor_independiente_id          BIGINT REFERENCES usuario (id),
    ADD COLUMN estado_revision_independiente     TEXT
        CHECK (estado_revision_independiente IN ('pendiente', 'aprobada', 'observada')),
    ADD COLUMN comentario_revision_independiente TEXT,
    ADD COLUMN enviado_revision_en               TIMESTAMPTZ,
    ADD COLUMN revisado_independiente_en         TIMESTAMPTZ,
    ADD COLUMN proveedor_seleccionado_ruc        CHAR(11),
    ADD COLUMN sustento_seleccion                TEXT,
    ADD CONSTRAINT revision_previa_cuatro_ojos
        CHECK (revisor_independiente_id IS NULL OR revisor_independiente_id <> evaluador_id),
    ADD CONSTRAINT revision_previa_evaluador_con_expediente
        CHECK (expediente_id IS NULL OR evaluador_id IS NOT NULL);

-- Una sola evaluación por expediente.
CREATE UNIQUE INDEX revision_previa_expediente_unica
    ON revision_previa (expediente_id) WHERE expediente_id IS NOT NULL;

-- Declaraciones y vínculos detectados entre funcionarios y postores.
CREATE TABLE conflicto_interes (
    id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    expediente_id      BIGINT NOT NULL REFERENCES expediente (id),
    revision_previa_id BIGINT REFERENCES revision_previa (id),
    persona_id         BIGINT NOT NULL REFERENCES persona (id),
    proveedor_ruc      CHAR(11),
    tipo               TEXT NOT NULL
                       CHECK (tipo IN ('declaracion_negativa', 'declaracion_conflicto', 'vinculo_detectado')),
    descripcion        TEXT NOT NULL CHECK (length(btrim(descripcion)) > 0),
    bloqueante         BOOLEAN NOT NULL DEFAULT false,
    estado             TEXT NOT NULL DEFAULT 'declarado'
                       CHECK (estado IN ('declarado', 'en_revision', 'mitigado', 'confirmado')),
    registrado_en      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_conflicto_interes_expediente ON conflicto_interes (expediente_id);
CREATE INDEX idx_conflicto_interes_persona ON conflicto_interes (persona_id);
