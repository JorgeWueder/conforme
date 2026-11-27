-- Permite guardar el proveedor elegido en el expediente apenas se aprueba la
-- revisión independiente (seleccion_aprobada), sin exigir emisión previa de orden en SIGA.
ALTER TABLE expediente DROP CONSTRAINT expediente_orden_completa;
ALTER TABLE expediente DROP CONSTRAINT expediente_orden_segun_estado;

ALTER TABLE expediente
    ADD CONSTRAINT expediente_orden_completa CHECK (
        (numero_orden IS NULL) = (fecha_orden IS NULL)
        AND (numero_orden IS NULL OR proveedor_id IS NOT NULL)),
    ADD CONSTRAINT expediente_orden_segun_estado CHECK (
        CASE
            WHEN estado_flujo IN ('requerimiento', 'tdr_observado', 'en_evaluacion_proveedores',
                                  'pendiente_revision_independiente')
                THEN proveedor_id IS NULL AND numero_orden IS NULL
            WHEN estado_flujo = 'seleccion_aprobada'
                THEN numero_orden IS NULL
            ELSE proveedor_id IS NOT NULL AND numero_orden IS NOT NULL
        END);
