-- F2 Conformidad: entregables, conformidad con evidencias, pagos y alertas.

CREATE TABLE entregable (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    expediente_id BIGINT NOT NULL REFERENCES expediente (id),
    numero        INTEGER NOT NULL CHECK (numero > 0),
    descripcion   TEXT NOT NULL,
    origen        TEXT NOT NULL DEFAULT 'manual' CHECK (origen IN ('manual', 'csv', 'ia')),
    UNIQUE (expediente_id, numero)
);

-- Una conformidad por expediente.
CREATE TABLE conformidad (
    id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    expediente_id      BIGINT NOT NULL UNIQUE REFERENCES expediente (id),
    conformante_id     BIGINT NOT NULL REFERENCES persona (id),
    fecha_conformidad  DATE NOT NULL,
    observaciones      TEXT NOT NULL DEFAULT '',
    penalidad_aplicada NUMERIC(14, 2) NOT NULL DEFAULT 0 CHECK (penalidad_aplicada >= 0),
    codigo_sello       TEXT UNIQUE,  -- se llena en F3
    registrada_en      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE conformidad_entregable (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    conformidad_id BIGINT NOT NULL REFERENCES conformidad (id),
    entregable_id  BIGINT NOT NULL REFERENCES entregable (id),
    cumplido       BOOLEAN NOT NULL,
    observacion    TEXT NOT NULL DEFAULT '',
    UNIQUE (conformidad_id, entregable_id)
);

CREATE TABLE evidencia (
    id                        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    conformidad_entregable_id BIGINT NOT NULL REFERENCES conformidad_entregable (id),
    nombre_archivo            TEXT NOT NULL,
    mime                      TEXT NOT NULL,
    tamano                    INTEGER NOT NULL CHECK (tamano > 0 AND tamano <= 5242880),
    sha256                    CHAR(64) NOT NULL,
    contenido                 BYTEA NOT NULL,
    subido_por                BIGINT NOT NULL REFERENCES persona (id),
    subido_en                 TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_evidencia_conformidad_entregable ON evidencia (conformidad_entregable_id);

CREATE TABLE pago (
    id                   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    expediente_id        BIGINT NOT NULL REFERENCES expediente (id),
    fecha_pago           DATE NOT NULL,
    monto                NUMERIC(14, 2) NOT NULL CHECK (monto > 0),
    penalidad_descontada NUMERIC(14, 2) NOT NULL DEFAULT 0 CHECK (penalidad_descontada >= 0),
    registrado_por       BIGINT NOT NULL REFERENCES persona (id),
    registrado_en        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_pago_expediente ON pago (expediente_id);

-- UNIQUE (expediente, regla, clave): reevaluar no duplica alertas.
CREATE TABLE alerta (
    id                   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    expediente_id        BIGINT NOT NULL REFERENCES expediente (id),
    regla                TEXT NOT NULL CHECK (regla IN ('R1', 'R2', 'R3', 'R4', 'R5')),
    clave                TEXT NOT NULL,
    severidad            TEXT NOT NULL CHECK (severidad IN ('alta', 'media')),
    explicacion          TEXT NOT NULL,
    datos                JSONB NOT NULL DEFAULT '{}'::jsonb,
    persona_implicada_id BIGINT REFERENCES persona (id),
    estado               TEXT NOT NULL DEFAULT 'abierta'
                         CHECK (estado IN ('abierta', 'con_descargo', 'cerrada', 'escalada')),
    creada_en            TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizada_en       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (expediente_id, regla, clave)
);
CREATE INDEX idx_alerta_estado ON alerta (estado);
CREATE INDEX idx_alerta_persona_implicada ON alerta (persona_implicada_id);

CREATE TABLE alerta_revision (
    id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    alerta_id BIGINT NOT NULL REFERENCES alerta (id),
    tipo      TEXT NOT NULL CHECK (tipo IN ('descargo', 'cierre', 'escalamiento')),
    autor_id  BIGINT NOT NULL REFERENCES persona (id),
    texto     TEXT NOT NULL CHECK (length(btrim(texto)) > 0),
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_alerta_revision_alerta ON alerta_revision (alerta_id);
