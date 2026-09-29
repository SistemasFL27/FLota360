"""Carga una flota de demostración para previsualizar el dashboard sin PostgreSQL ni APIs externas."""

from datetime import datetime, timedelta, timezone

from database import SessionLocal, engine, Base, ensure_columns
from models import Unidad, RegistroTelemetria, OrdenTrabajo

FLETA_DEMO = [
    {
        "patente": "GPV408",
        "marca": "Mercedes-Benz",
        "modelo": "Actros 2545",
        "empresa": "Flecha Logística",
        "km_service": 286400,
        "delta_km": 11240,
        "km_mes": 6840,
        "consumo": 32.4,
        "litros": 2216,
        "fuente": "Excel_Septiembre",
        "ot": "OT-18421",
        "comments": "Service 10.000 km + cambio de filtros",
    },
    {
        "patente": "AB123CD",
        "marca": "Scania",
        "modelo": "R450",
        "empresa": "Flecha Logística",
        "km_service": 412100,
        "delta_km": 9480,
        "km_mes": 7120,
        "consumo": 29.8,
        "litros": 2121,
        "fuente": "FleetComplete_API",
        "ot": "OT-18390",
        "comments": "Revisión de frenos y alineación",
    },
    {
        "patente": "AD456EF",
        "marca": "Volvo",
        "modelo": "FH 460",
        "empresa": "Flecha Logística",
        "km_service": 198750,
        "delta_km": 3210,
        "km_mes": 4980,
        "consumo": 31.1,
        "litros": 1548,
        "fuente": "Excel_Septiembre",
        "ot": "OT-18502",
        "comments": "Service preventivo en sucursal Pilar",
    },
    {
        "patente": "AE789GH",
        "marca": "Iveco",
        "modelo": "Stralis 440",
        "empresa": "Flecha Logística",
        "km_service": 355020,
        "delta_km": 12880,
        "km_mes": 8010,
        "consumo": 34.6,
        "litros": 2771,
        "fuente": "Maxtracker_Sim",
        "ot": "OT-18211",
        "comments": "Cambio de aceite y correa",
    },
    {
        "patente": "AF012IJ",
        "marca": "Ford",
        "modelo": "Cargo 1723",
        "empresa": "Flecha Logística",
        "km_service": 142300,
        "delta_km": 910,
        "km_mes": 2140,
        "consumo": 22.5,
        "litros": 481,
        "fuente": "Excel_Septiembre",
        "ot": "OT-18540",
        "comments": "Service reciente — unidad operativa",
    },
    {
        "patente": "AG345KL",
        "marca": "Volkswagen",
        "modelo": "Constellation 24.280",
        "empresa": "Flecha Logística",
        "km_service": 267890,
        "delta_km": 9650,
        "km_mes": 5530,
        "consumo": 28.9,
        "litros": 1598,
        "fuente": "Geotab",
        "ot": "OT-18355",
        "comments": "Inspección de suspensión",
    },
    {
        "patente": "AH678MN",
        "marca": "Mercedes-Benz",
        "modelo": "Atego 1726",
        "empresa": "Flecha Logística",
        "km_service": 98040,
        "delta_km": 5400,
        "km_mes": 3890,
        "consumo": 24.2,
        "litros": 941,
        "fuente": "Excel_Septiembre",
        "ot": "OT-18488",
        "comments": "Cambio de pastillas delanteras",
    },
    {
        "patente": "AJ901OP",
        "marca": "Scania",
        "modelo": "P320",
        "empresa": "Flecha Logística",
        "km_service": 221500,
        "delta_km": 0,
        "km_mes": 0,
        "consumo": None,
        "litros": None,
        "fuente": None,
        "ot": "OT-18102",
        "comments": "Unidad en taller — sin telemetría reciente",
        "sin_gps": True,
    },
]


def seed():
    Base.metadata.create_all(bind=engine)
    ensure_columns()
    db = SessionLocal()
    if db.query(Unidad).count() > 0:
        print("La base ya tiene unidades. No se vuelve a sembrar.")
        db.close()
        return

    ahora = datetime.now(timezone.utc)
    for i, item in enumerate(FLETA_DEMO):
        unidad = Unidad(
            patente_normalizada=item["patente"],
            marca=item["marca"],
            modelo=item["modelo"],
            empresa=item["empresa"],
            cloudfleet_id=item["patente"],
        )
        db.add(unidad)
        db.flush()

        db.add(OrdenTrabajo(
            number=item["ot"],
            vehicle_code=item["patente"],
            odometer=item["km_service"],
            status="closed",
            closed_at=ahora - timedelta(days=20 + i * 7),
            comments=item["comments"],
            total_cost=180000 + i * 25000,
        ))

        if item.get("sin_gps"):
            continue

        db.add(RegistroTelemetria(
            unidad_id=unidad.id,
            odometro_gps=item["km_service"] + item["delta_km"],
            km_recorridos_mes=item["km_mes"],
            consumo_l100km=item["consumo"],
            litros_combustible=item["litros"],
            velocidad=0.0 if i % 3 == 0 else 68.0,
            latitud=-34.6037 + i * 0.08,
            longitud=-58.3816 - i * 0.05,
            fuente=item["fuente"],
            fecha_lectura=ahora - timedelta(hours=i),
        ))

    db.commit()
    total = db.query(Unidad).count()
    db.close()
    print(f"Sembradas {total} unidades de demostración.")


if __name__ == "__main__":
    seed()
