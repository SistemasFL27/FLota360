from sqlalchemy import text
from database import engine

def actualizar():
    with engine.begin() as conn:
        try:
            conn.execute(text("ALTER TABLE registro_telemetria ADD COLUMN litros_combustible FLOAT;"))
            print("✅ Columna 'litros_combustible' agregada a PostgreSQL.")
        except Exception as e:
            print(f"⚡ Omitido: {e}")

if __name__ == "__main__":
    actualizar()