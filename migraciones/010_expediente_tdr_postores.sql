-- Fase 1: el expediente es el eje del ciclo. Nace como requerimiento (sin proveedor ni
-- orden), pasa por la evaluación de posibles proveedores y recién al aprobarse la
-- selección se fija el proveedor y la orden.

ALTER TABLE expediente
    ALTER COLUMN proveedor_id DROP NOT NULL,
    ALTER COLUMN numero_orden DROP NOT NULL,
    ALTER COLUMN fecha_orden DROP NOT NULL,
    ADD COLUMN estado_flujo TEXT NOT NULL DEFAULT 'en_ejecucion';

-- Estado de los expedientes que ya existían, deducido de lo registrado.
UPDATE expediente x SET estado_flujo = CASE
    WHEN EXISTS (SELECT 1 FROM pago p WHERE p.expediente_id = x.id) THEN 'pagado'
    WHEN (SELECT b.accion FROM bitacora b
          WHERE b.expediente_id = x.id AND b.accion IN ('conformidad.revisada', 'conformidad.devuelta')
          ORDER BY b.id DESC LIMIT 1) = 'conformidad.devuelta' THEN 'conformidad_devuelta'
    WHEN EXISTS (SELECT 1 FROM bitacora b
                 WHERE b.expediente_id = x.id AND b.accion = 'conformidad.revisada') THEN 'derivado_tesoreria'
    WHEN EXISTS (SELECT 1 FROM conformidad c WHERE c.expediente_id = x.id) THEN 'conformidad_emitida'
    ELSE 'en_ejecucion'
END;

ALTER TABLE expediente
    ADD CONSTRAINT expediente_estado_flujo_check CHECK (estado_flujo IN (
        'requerimiento', 'tdr_observado', 'en_evaluacion_proveedores',
        'pendiente_revision_independiente', 'seleccion_aprobada', 'orden_registrada',
        'en_ejecucion', 'observado', 'conformidad_emitida', 'conformidad_devuelta',
        'derivado_tesoreria', 'pagado')),
    -- Proveedor, número y fecha de la orden se fijan juntos.
    ADD CONSTRAINT expediente_orden_completa CHECK (
        (proveedor_id IS NULL) = (numero_orden IS NULL)
        AND (numero_orden IS NULL) = (fecha_orden IS NULL)),
    -- Antes de la orden el expediente no puede tener proveedor; después, debe tenerlo.
    ADD CONSTRAINT expediente_orden_segun_estado CHECK (
        (estado_flujo IN ('requerimiento', 'tdr_observado', 'en_evaluacion_proveedores',
                          'pendiente_revision_independiente', 'seleccion_aprobada'))
        = (proveedor_id IS NULL));
CREATE INDEX idx_expediente_estado_flujo ON expediente (estado_flujo);

-- Posibles proveedores (postores) contemplados en el expediente.
CREATE TABLE expediente_postor (
    id                   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    expediente_id        BIGINT NOT NULL REFERENCES expediente (id),
    ruc                  CHAR(11) NOT NULL,
    razon_social         TEXT NOT NULL CHECK (length(btrim(razon_social)) > 0),
    monto_cotizado       NUMERIC(14, 2) NOT NULL CHECK (monto_cotizado > 0),
    plazo_dias           INTEGER NOT NULL CHECK (plazo_dias > 0),
    contacto_nombre      TEXT,
    contacto_correo      TEXT,
    contacto_telefono    TEXT,
    direccion            TEXT,
    proforma_ref         TEXT,
    cumple_tdr           BOOLEAN,
    estado               TEXT NOT NULL DEFAULT 'pendiente'
                         CHECK (estado IN ('pendiente', 'analizado', 'consolidado', 'descartado', 'seleccionado')),
    motivo_descarte      TEXT,
    analisis_dimensiones JSONB NOT NULL DEFAULT '{}'::jsonb,
    informe_consolidado  JSONB,
    notas_encargado      TEXT NOT NULL DEFAULT '',
    registrado_por       BIGINT NOT NULL REFERENCES persona (id),
    analizado_en         TIMESTAMPTZ,
    consolidado_en       TIMESTAMPTZ,
    creado_en            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (expediente_id, ruc)
);
CREATE INDEX idx_expediente_postor_ruc ON expediente_postor (ruc);

-- Revisión documental y forense (Fase 3): documentos de postores y análisis de Benford.
CREATE TABLE revision_documental (
    id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ambito             TEXT NOT NULL CHECK (ambito IN ('documento_proveedor', 'expediente', 'transversal')),
    expediente_id      BIGINT REFERENCES expediente (id),
    postor_id          BIGINT REFERENCES expediente_postor (id),
    archivos           JSONB NOT NULL DEFAULT '[]'::jsonb,
    resultados_bloques JSONB NOT NULL DEFAULT '{}'::jsonb,
    benford            JSONB,
    veredicto          TEXT CHECK (veredicto IN ('conforme', 'revisar', 'anomalia')),
    resumen_agente     TEXT,
    creado_por         BIGINT NOT NULL REFERENCES persona (id),
    creado_en          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_revision_documental_expediente ON revision_documental (expediente_id);

-- Observaciones técnicas al TDR (Fase 4): las corrige o justifica el área usuaria.
CREATE TABLE tdr_observacion (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    expediente_id  BIGINT NOT NULL REFERENCES expediente (id),
    origen         TEXT NOT NULL CHECK (origen IN ('ia', 'abastecimiento')),
    autor_id       BIGINT REFERENCES persona (id),
    detalle        TEXT NOT NULL CHECK (length(btrim(detalle)) > 0),
    severidad      TEXT NOT NULL CHECK (severidad IN ('bloqueante', 'advertencia')),
    estado         TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'corregida', 'justificada')),
    respuesta_area TEXT,
    respondido_por BIGINT REFERENCES persona (id),
    respondido_en  TIMESTAMPTZ,
    creado_en      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_tdr_observacion_expediente ON tdr_observacion (expediente_id);
