-- Habilita reglas preventivas de proveedores (P1–P4) y forenses documentales (D1–D3).
ALTER TABLE alerta DROP CONSTRAINT alerta_regla_check;
ALTER TABLE alerta ADD CONSTRAINT alerta_regla_check
    CHECK (regla IN (
        'R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7', 'R8',
        'P1', 'P2', 'P3', 'P4',
        'D1', 'D2', 'D3',
        'OCI'
    ));
