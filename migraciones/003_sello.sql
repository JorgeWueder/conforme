-- F3: el sello guarda el último registro de bitácora que cubre la conformidad
-- (y sus evidencias). Si ese registro desaparece o cambia, la verificación lo detecta
-- aunque la cadena, por sí sola, no pueda señalar el borrado de los últimos registros.
ALTER TABLE conformidad
    ADD COLUMN sello_bitacora_id BIGINT,
    ADD COLUMN sello_hash        CHAR(64);

ALTER TABLE conformidad
    ADD CONSTRAINT conformidad_sello_completo
    CHECK ((codigo_sello IS NULL) = (sello_hash IS NULL)
       AND (sello_hash IS NULL) = (sello_bitacora_id IS NULL));
