ALTER TABLE expediente
    ADD COLUMN proyecto_referencia TEXT,
    ADD COLUMN conformidad_plazo_especial BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE pago ADD COLUMN referencia_siaf TEXT;
