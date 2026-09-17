from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Reemplazá TU_CONTRASEÑA por la clave que definiste al instalar PostgreSQL
# Si no creaste una base propia todavía, usá la base por defecto "postgres"
DATABASE_URL = "postgresql://postgres:Flechalog@localhost:5432/postgres"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()