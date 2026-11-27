-- Las alertas ya existentes reciben el ámbito y el carácter bloqueante de su regla.
-- Las actuaciones de seguimiento OCI nunca bloquean decisiones operativas.
ALTER TABLE alerta DROP CONSTRAINT alerta_regla_check;
ALTER TABLE alerta ADD CONSTRAINT alerta_regla_check
    CHECK (regla IN ('R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7', 'R8', 'OCI'));

UPDATE alerta
SET ambito = CASE WHEN regla IN ('R6', 'R7') THEN 'preventiva_dec'
                  ELSE 'operativa_tesoreria' END,
    bloqueante = regla IN ('R1', 'R4', 'R5')
WHERE regla IN ('R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7', 'R8');

CREATE INDEX idx_alerta_ambito_estado ON alerta (ambito, estado, creada_en DESC);
