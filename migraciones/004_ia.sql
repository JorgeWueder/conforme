-- F4: lectura de términos de referencia con IA. Nada entra a `entregable` sin
-- aprobación humana: la propuesta vive aquí hasta que una persona la aprueba o rechaza.
CREATE TABLE extraccion_ia (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    expediente_id  BIGINT NOT NULL REFERENCES expediente (id),
    archivo_nombre TEXT NOT NULL,
    archivo_sha256 CHAR(64) NOT NULL,
    resultado      JSONB NOT NULL,
    origen         TEXT NOT NULL CHECK (origen IN ('modelo', 'respaldo')),
    aviso          TEXT,
    estado         TEXT NOT NULL DEFAULT 'propuesta'
                   CHECK (estado IN ('propuesta', 'aprobada', 'rechazada')),
    creado_por     BIGINT NOT NULL REFERENCES persona (id),
    creado_en      TIMESTAMPTZ NOT NULL DEFAULT now(),
    revisado_por   BIGINT REFERENCES persona (id),
    revisado_en    TIMESTAMPTZ,
    CHECK ((estado = 'propuesta') = (revisado_por IS NULL))
);
CREATE INDEX extraccion_ia_expediente_idx ON extraccion_ia (expediente_id);
