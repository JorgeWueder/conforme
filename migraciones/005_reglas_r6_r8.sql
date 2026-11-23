-- Reglas entre expedientes y de fechas: R6 (proveedor recurrente), R7 (compras similares
-- sucesivas) y R8 (fechas incoherentes). Solo amplía las reglas admitidas en `alerta`.
ALTER TABLE alerta DROP CONSTRAINT alerta_regla_check;
ALTER TABLE alerta
    ADD CONSTRAINT alerta_regla_check
    CHECK (regla IN ('R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7', 'R8'));
