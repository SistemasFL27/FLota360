import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base

class Unidad(Base):
    __tablename__ = "unidades"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patente_normalizada = Column(String(20), unique=True, index=True, nullable=False)
    marca = Column(String(50), nullable=True)
    modelo = Column(String(50), nullable=True)
    empresa = Column(String(100), nullable=True)

    telemetria = relationship("RegistroTelemetria", back_populates="unidad", cascade="all, delete-orphan")

class RegistroTelemetria(Base):
    __tablename__ = "registro_telemetria"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    unidad_id = Column(UUID(as_uuid=True), ForeignKey("unidades.id"), nullable=False)
    odometro_gps = Column(Float, nullable=True)
    km_recorridos_mes = Column(Float, nullable=True)
    consumo_l100km = Column(Float, nullable=True)
    litros_combustible = Column(Float, nullable=True) # NUEVO CAMPO
    velocidad = Column(Float, default=0.0)
    fuente = Column(String(50), nullable=False)
    fecha_lectura = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    unidad = relationship("Unidad", back_populates="telemetria")

class OrdenTrabajo(Base):
    __tablename__ = "ordenes_trabajo"
    number = Column(String(50), primary_key=True)
    vehicle_code = Column(String(20), index=True, nullable=False)
    odometer = Column(Float, nullable=True)
    status = Column(String(20), default="closed")
    closed_at = Column(DateTime, nullable=True)
    comments = Column(Text, nullable=True)
    total_cost = Column(Float, default=0.0)
    synced_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))