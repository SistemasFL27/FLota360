import requests
import re
from datetime import datetime, timezone
from database import engine, SessionLocal, Base
from models import Unidad, RegistroTelemetria

# Credenciales de Fleet Complete Unity
USERNAME = "FlotaArrow"
PASSWORD = "Power2026"

AUTH_URL = "https://api.fleetcomplete.com/login/token"
USERINFO_URL = "https://api.fleetcomplete.com/login/userinfo"
GRAPHQL_URL = "https://api.fleetcomplete.com/graphql"

def normalizar_patente(patente: str) -> str:
    return re.sub(r'[^A-Z0-9]', '', str(patente).upper()) if patente else ""

def obtener_autenticacion():
    """Paso 1 y 2: Obtener access_token y userId"""
    try:
        # Request 1: Token
        resp_token = requests.post(AUTH_URL, data={"username": USERNAME, "password": PASSWORD})
        if resp_token.status_code != 200:
            print(f"[FLEET COMPLETE] ❌ Error de Token ({resp_token.status_code}): {resp_token.text}")
            return None, None
        
        token = resp_token.json().get("access_token")

        # Request 2: UserInfo
        headers_user = {"Authorization": f"Bearer {token}"}
        resp_user = requests.get(USERINFO_URL, headers=headers_user)
        if resp_user.status_code != 200:
            print(f"[FLEET COMPLETE] ❌ Error UserInfo ({resp_user.status_code}): {resp_user.text}")
            return token, None

        user_info = resp_user.json()
        user_id = user_info[0].get("userId") if isinstance(user_info, list) and user_info else None
        
        return token, user_id
    except Exception as e:
        print(f"[FLEET COMPLETE] ❌ Error de conexión en auth: {e}")
        return None, None

def sincronizar_fleetcomplete():
    """Paso 3: Consulta GraphQL y persistencia en PostgreSQL"""
    Base.metadata.create_all(bind=engine)
    token, user_id = obtener_autenticacion()
    
    if not token or not user_id:
        print("[FLEET COMPLETE] ⚠️ No se pudo completar el inicio de sesión.")
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "userId": user_id,
        "Content-Type": "application/json"
    }

    # Query para traer patentes, odómetro y última ubicación GPS
    query = """
    query GetActiveVehicles {
      getActiveVehicles {
        id
        licensePlate
        name
        lastOdometer
        latestData {
          gps {
            latitude
            longitude
            speed
          }
          odometer {
            value
          }
        }
      }
    }
    """

    print("[FLEET COMPLETE] Consultando telemetría en tiempo real vía GraphQL...")
    resp = requests.post(GRAPHQL_URL, headers=headers, json={"query": query})

    if resp.status_code != 200:
        print(f"[FLEET COMPLETE] ❌ Error GraphQL HTTP {resp.status_code}: {resp.text}")
        return

    vehiculos = resp.json().get("data", {}).get("getActiveVehicles", [])
    if not vehiculos:
        print("[FLEET COMPLETE] Sin vehículos devueltos en la consulta.")
        return

    db = SessionLocal()
    registros_insertados = 0
    omitidos = 0

    for v in vehiculos:
        patente_raw = v.get("licensePlate") or v.get("name")
        patente_limpia = normalizar_patente(patente_raw)

        if not patente_limpia:
            omitidos += 1
            continue

        # Matcheo con Padrón Maestro Ficha 360
        unidad = db.query(Unidad).filter(Unidad.patente_normalizada == patente_limpia).first()
        if not unidad:
            omitidos += 1
            continue

        # Extraer odómetro y coordenadas
        latest_data = v.get("latestData") or {}
        odometro_val = (latest_data.get("odometer") or {}).get("value") or v.get("lastOdometer") or 0.0

        gps_data = latest_data.get("gps") or {}
        lat = gps_data.get("latitude")
        lon = gps_data.get("longitude")

        # Conversión de minutos de arco a grados decimales si la API los entrega en formato bruto
        if lat and abs(lat) > 90:
            lat = lat / 60.0
        if lon and abs(lon) > 180:
            lon = lon / 60.0

        registro = RegistroTelemetria(
            unidad_id=unidad.id,
            odometro_gps=float(odometro_val),
            latitud=float(lat) if lat is not None else None,
            longitud=float(lon) if lon is not None else None,
            velocidad=float(gps_data.get("speed") or 0.0),
            fuente="FleetComplete_API",
            fecha_lectura=datetime.now(timezone.utc)
        )
        db.add(registro)
        registros_insertados += 1

    db.commit()
    db.close()
    print(f"[FLEET COMPLETE] ✅ {registros_insertados} lecturas de GPS reales vinculadas ({omitidos} sin coincidencia).")

if __name__ == "__main__":
    sincronizar_fleetcomplete()