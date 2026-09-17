import requests
import re
import time
from database import engine, SessionLocal, Base
from models import Unidad

# Recordá poner tu clave real
API_KEY = "rzFXdCL.Ophl4ThQXVY0LU-3D4X5pLuvAQRt_r3SA"
BASE_URL = "https://fleet.cloudfleet.com/api/v1"

def normalizar_patente(patente: str) -> str:
    return re.sub(r'[^A-Z0-9]', '', patente.upper()) if patente else ""

def sincronizar_vehiculos_cloudfleet():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    url_actual = f"{BASE_URL}/vehicles/"
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    print("[VEHÍCULOS] Consultando padrón completo en Cloudfleet (paginado)...")
    
    total_procesados = 0
    nuevos = 0
    pagina = 1

    try:
        while url_actual:
            print(f"Consultando página {pagina} de vehículos...")
            respuesta = requests.get(url_actual, headers=headers)

            # Manejo de Rate Limit
            if respuesta.status_code == 429:
                tiempo_espera = int(respuesta.headers.get("Retry-After", 10))
                print(f"Límite alcanzado. Esperando {tiempo_espera}s...")
                time.sleep(tiempo_espera)
                continue

            if respuesta.status_code != 200:
                print(f"Error HTTP {respuesta.status_code}: {respuesta.text}")
                break

            vehiculos = respuesta.json()
            if not vehiculos:
                break

            for item in vehiculos:
                code_raw = item.get("code") or item.get("vehicleCode")
                patente_limpia = normalizar_patente(code_raw)
                
                if not patente_limpia:
                    continue
                
                # Upsert en la base
                unidad_existente = db.query(Unidad).filter(Unidad.patente_normalizada == patente_limpia).first()
                
                if not unidad_existente:
                    nueva_unidad = Unidad(
                        patente_normalizada=patente_limpia,
                        cloudfleet_id=str(code_raw)
                    )
                    db.add(nueva_unidad)
                    nuevos += 1
                
                total_procesados += 1

            db.commit()

            # Leer si existe una página siguiente en la API
            next_page = respuesta.headers.get("X-NextPage") or respuesta.headers.get("x-nextpage")
            if next_page and next_page != "null":
                url_actual = next_page.strip('"')
                pagina += 1
                time.sleep(1)
            else:
                url_actual = None

        print(f"\n[VEHÍCULOS] ✅ Sincronización completa.")
        print(f"Total vehículos procesados: {total_procesados} | Nuevas unidades registradas: {nuevos}")

    except Exception as e:
        print(f"[VEHÍCULOS] Error de conexión: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    sincronizar_vehiculos_cloudfleet()