-- Fase 1 (cimientos de la Fase 5): evidencia exigida por entregable, conformidad
-- versionable con revisión de Abastecimiento y verificación previa al pago.

ALTER TABLE entregable ADD COLUMN criterio_evidencia TEXT;

ALTER TABLE conformidad
    ADD COLUMN version                 INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    ADD COLUMN vigente                 BOOLEAN NOT NULL DEFAULT true,
    ADD COLUMN sustento_penalidad      TEXT,
    ADD COLUMN verificacion_evidencias JSONB,
    ADD COLUMN estado_revision_dec     TEXT NOT NULL DEFAULT 'pendiente'
        CHECK (estado_revision_dec IN ('pendiente', 'favorable', 'devuelta')),
    ADD COLUMN referencia_derivacion   TEXT,
    ADD COLUMN motivo_revision_dec     TEXT,
    ADD COLUMN revisado_dec_por        BIGINT REFERENCES persona (id),
    ADD COLUMN revisado_dec_en         TIMESTAMPTZ;

-- Revisiones de Abastecimiento ya registradas en la bitácora.
UPDATE conformidad c SET
    estado_revision_dec = CASE WHEN b.accion = 'conformidad.revisada' THEN 'favorable' ELSE 'devuelta' END,
    referencia_derivacion = b.detalle ->> 'referencia_derivacion',
    motivo_revision_dec = b.detalle ->> 'motivo',
    revisado_dec_por = b.actor_id,
    revisado_dec_en = b.ts
FROM (
    SELECT DISTINCT ON (expediente_id) expediente_id, accion, detalle, actor_id, ts
    FROM bitacora WHERE accion IN ('conformidad.revisada', 'conformidad.devuelta')
    ORDER BY expediente_id, id DESC
) b
WHERE b.expediente_id = c.expediente_id;

-- Puede haber varias versiones por expediente, pero solo una vigente.
ALTER TABLE conformidad DROP CONSTRAINT conformidad_expediente_id_key;
ALTER TABLE conformidad ADD CONSTRAINT conformidad_version_unica UNIQUE (expediente_id, version);
CREATE UNIQUE INDEX conformidad_vigente_unica ON conformidad (expediente_id) WHERE vigente;

CREATE TABLE verificacion_pago (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    expediente_id    BIGINT NOT NULL REFERENCES expediente (id),
    verificado_por   BIGINT NOT NULL REFERENCES persona (id),
    checklist        JSONB NOT NULL,
    bloqueos_activos JSONB NOT NULL DEFAULT '[]'::jsonb,
    apto_para_pago   BOOLEAN NOT NULL,
    creado_en        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_verificacion_pago_expediente ON verificacion_pago (expediente_id);

ALTER TABLE pago ADD COLUMN verificacion_pago_id BIGINT REFERENCES verificacion_pago (id);
