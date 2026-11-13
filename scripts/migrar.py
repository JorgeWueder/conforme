"""Aplica las migraciones pendientes.  Uso: python -m scripts.migrar"""
from conforme import db, migraciones

if __name__ == "__main__":
    aplicadas = migraciones.aplicar(db.obtener_engine())
    print("Migraciones aplicadas:", ", ".join(aplicadas) if aplicadas else "ninguna (ya al día)")
