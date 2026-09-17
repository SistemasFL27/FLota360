import re
from datetime import datetime, timezone
from database import engine, SessionLocal, Base
from models import Unidad, RegistroTelemetria

def normalizar_patente(patente: str) -> str:
    return re.sub(r'[^A-Z0-9]', '', patente.upper()) if patente else ""

def ingestar_lecturas_gps(datos_gps: list):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    registros_insertados = 0

    for lectura in datos_gps:
        patente_limpia = normalizar_patente(lectura.get("patente"))
        unidad = db.query(Unidad).filter(Unidad.patente_normalizada == patente_limpia).first()

        if unidad:
            nuevo_registro = RegistroTelemetria(
                unidad_id=unidad.id,
                odometro_gps=lectura.get("odometro"),
                latitud=lectura.get("latitud"),
                longitud=lectura.get("longitud"),
                velocidad=lectura.get("velocidad", 0.0),
                fuente=lectura.get("proveedor", "GPS_Satelital"),
                fecha_lectura=datetime.now(timezone.utc)
            )
            db.add(nuevo_registro)
            registros_insertados += 1
        else:
            print(f"[TELEMETRÍA] ⚠️ Patente {patente_limpia} no encontrada en padrón maestro. Omitiendo.")

    db.commit()
    db.close()
    print(f"[TELEMETRÍA] ✅ {registros_insertados} lecturas de GPS asociadas exitosamente.")

if __name__ == "__main__":
    # Lote de prueba de proveedor GPS
    lote_ejemplo = [
        {"patente": "GPV408", "odometro": 898120.5, "latitud": -34.6037, "longitud": -58.3816, "velocidad": 62.0, "proveedor": "Geotab"},
        {"patente": "GPV-408", "odometro": 898155.0, "latitud": -34.6500, "longitud": -58.4000, "velocidad": 0.0, "proveedor": "Geotab"}
    ]
    ingestar_lecturas_gps(lote_ejemplo)