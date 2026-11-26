CREATE INDEX prevencion_registro_entidad_fecha
    ON prevencion_registro (edicion_id, (datos ->> 'entidad_ruc'), (datos ->> 'fecha'))
    WHERE (datos ->> 'entidad_ruc') IS NOT NULL;
