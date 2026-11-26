-- Rol de Abastecimiento (DEC en el proceso de la UNT): comunica observaciones y revisa la conformidad.
ALTER TABLE usuario DROP CONSTRAINT usuario_rol_check;
ALTER TABLE usuario ADD CONSTRAINT usuario_rol_check
    CHECK (rol IN ('area_usuaria', 'tesoreria', 'auditor', 'abastecimiento'));
