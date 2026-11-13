-- F1 Núcleo: catálogos, expedientes y bitácora encadenada.

CREATE TABLE area (
    id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre TEXT NOT NULL,
    sigla  TEXT NOT NULL UNIQUE
);

CREATE TABLE persona (
    id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dni       CHAR(8) NOT NULL UNIQUE,
    nombres   TEXT NOT NULL,
    apellidos TEXT NOT NULL,
    cargo     TEXT NOT NULL,
    area_id   BIGINT NOT NULL REFERENCES area (id)
);
CREATE INDEX idx_persona_area ON persona (area_id);

CREATE TABLE usuario (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    persona_id    BIGINT NOT NULL UNIQUE REFERENCES persona (id),
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    rol           TEXT NOT NULL CHECK (rol IN ('area_usuaria', 'tesoreria', 'auditor'))
);

CREATE TABLE proveedor (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ruc          CHAR(11) NOT NULL UNIQUE,
    razon_social TEXT NOT NULL
);

CREATE TABLE expediente (
    id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo                  TEXT NOT NULL UNIQUE,
    tipo                    TEXT NOT NULL CHECK (tipo IN ('bien', 'servicio')),
    descripcion             TEXT NOT NULL,
    area_id                 BIGINT NOT NULL REFERENCES area (id),
    proveedor_id            BIGINT NOT NULL REFERENCES proveedor (id),
    solicitante_id          BIGINT NOT NULL REFERENCES persona (id),
    numero_orden            TEXT NOT NULL,
    fecha_requerimiento     DATE NOT NULL,
    fecha_orden             DATE NOT NULL,
    fecha_inicio_prestacion DATE,
    plazo_dias              INTEGER NOT NULL CHECK (plazo_dias > 0),
    fecha_entrega_real      DATE,
    monto                   NUMERIC(14, 2) NOT NULL CHECK (monto > 0),
    creado_en               TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_expediente_area ON expediente (area_id);
CREATE INDEX idx_expediente_proveedor ON expediente (proveedor_id);
CREATE INDEX idx_expediente_solicitante ON expediente (solicitante_id);

-- Bitácora: solo se insertan filas. Cada fila guarda el hash de la anterior.
CREATE TABLE bitacora (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ts               TIMESTAMPTZ NOT NULL,
    actor_id         BIGINT REFERENCES persona (id),  -- NULL = sistema
    accion           TEXT NOT NULL,
    entidad          TEXT NOT NULL,
    entidad_id       BIGINT,
    expediente_id    BIGINT REFERENCES expediente (id),
    detalle          JSONB NOT NULL DEFAULT '{}'::jsonb,
    documento_sha256 CHAR(64),
    hash_anterior    CHAR(64) NOT NULL,
    hash             CHAR(64) NOT NULL UNIQUE
);
CREATE INDEX idx_bitacora_expediente ON bitacora (expediente_id, id);

-- Etiquetas de anomalías sembradas, para medir detección.
-- El motor de reglas NO lee esta tabla (lo verifica una prueba).
CREATE TABLE anomalia_sembrada (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    expediente_id BIGINT NOT NULL REFERENCES expediente (id),
    regla         TEXT NOT NULL,
    nota          TEXT
);
