-- Fase 3: documentos que presentan los postores (cotizaciones, presupuestos, propuestas,
-- declaraciones juradas, certificados). Se guardan para el análisis documental y forense;
-- su huella SHA-256 permite detectar archivos reciclados entre expedientes.
CREATE TABLE documento_postor (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    expediente_id  BIGINT NOT NULL REFERENCES expediente (id),
    postor_id      BIGINT NOT NULL REFERENCES expediente_postor (id) ON DELETE CASCADE,
    tipo           TEXT NOT NULL CHECK (tipo IN ('cotizacion', 'presupuesto', 'propuesta_tecnica',
                                                 'declaracion_jurada', 'certificado', 'otro')),
    nombre_archivo TEXT NOT NULL,
    mime           TEXT NOT NULL,
    tamano         INTEGER NOT NULL CHECK (tamano > 0 AND tamano <= 5242880),
    sha256         CHAR(64) NOT NULL,
    contenido      BYTEA NOT NULL,
    subido_por     BIGINT NOT NULL REFERENCES persona (id),
    subido_en      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_documento_postor_expediente ON documento_postor (expediente_id);
CREATE INDEX idx_documento_postor_sha256 ON documento_postor (sha256);
