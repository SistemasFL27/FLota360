import requests
import time
import re
from datetime import datetime, timedelta, timezone
from database import engine, SessionLocal, Base
from models import OrdenTrabajo

API_KEY = "rzFXdCL.Ophl4ThQXVY0LU-3D4X5pLuvAQRt_r3SA"
BASE_URL = "https://fleet.cloudfleet.com/api/v1"

def normalizar_patente(patente: str) -> str:
    return re.sub(r'[^A-Z0-9]', '', str(patente).upper()) if patente else ""

def sincronizar_cloudfleet():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    hoy = datetime.now(timezone.utc)
    hace_365_dias = hoy - timedelta(days=365)
    
    url_actual = f"{BASE_URL}/work-orders/?status=closed&createdAtFrom={hace_365_dias.strftime('%Y-%m-%dT%H:%M:%SZ')}&createdAtTo={hoy.strftime('%Y-%m-%dT%H:%M:%SZ')}"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}
    
    total_procesados = 0
    print("Descargando historial de Cloudfleet...")

    while url_actual:
        respuesta = requests.get(url_actual, headers=headers)
        if respuesta.status_code == 429:
            time.sleep(int(respuesta.headers.get("Retry-After", 10)))
            continue
        if respuesta.status_code != 200:
            break

        ordenes = respuesta.json()
        if not ordenes: break

        for item in ordenes:
            patente_limpia = normalizar_patente(item.get("vehicleCode"))
            ot_existente = db.query(OrdenTrabajo).filter(OrdenTrabajo.number == item.get("number")).first()
            
            if ot_existente:
                ot_existente.status = item.get("status")
                ot_existente.odometer = item.get("odometer")
            else:
                nueva_ot = OrdenTrabajo(
                    number=item.get("number"),
                    vehicle_code=patente_limpia,
                    status=item.get("status"),
                    odometer=item.get("odometer")
                )
                db.add(nueva_ot)
            total_procesados += 1

        db.commit()
        next_page = respuesta.headers.get("X-NextPage") or respuesta.headers.get("x-nextpage")
        if next_page and next_page != "null":
            url_actual = next_page.strip('"')
            time.sleep(1)
        else:
            url_actual = None

    db.close()
    print(f"✅ Cloudfleet restaurado. {total_procesados} órdenes guardadas.")

if __name__ == "__main__":
    sincronizar_cloudfleet()