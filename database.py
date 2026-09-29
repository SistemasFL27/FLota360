import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./flota360.db")
connect_args = {"check_same_thread": False, "timeout": 30} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_columns() -> None:
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "unidades" not in inspector.get_table_names():
        return
    existentes = {col["name"] for col in inspector.get_columns("unidades")}
    nuevas = {
        "ypf_device_id": "VARCHAR(200)",
        "ypf_automotor_id": "VARCHAR(200)",
        "ypf_imei": "VARCHAR(40)",
    }
    with engine.begin() as conn:
        for nombre, tipo in nuevas.items():
            if nombre not in existentes:
                conn.execute(text(f"ALTER TABLE unidades ADD COLUMN {nombre} {tipo}"))
