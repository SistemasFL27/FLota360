import random
from datetime import datetime, timezone
from database import SessionLocal
from models import Unidad, OrdenTrabajo, RegistroTelemetria

# Coordenadas reales de corredores logísticos (CABA, Pilar, Rosario, Córdoba, San Nicolás)
PUNTOS_RUTA = [
    (-34.6037, -58.3816),  # CABA
    (-34.4532, -58.8682),  # Base Pilar
    (-32.9468, -60.6393),  # CD Rosario
    (-31.4201, -64.1888),  # Córdoba
    (-33.3333, -60.2167),  # San Nicolás (RN9 km 218)
    (-34.6500, -58.4000)   # Avellaneda
]

def simular_telemetria_masiva():
    db = SessionLocal()
    unidades = db.query(Unidad).all()
    
    print(f"[SIMULADOR] Generando tramas GPS para {len(unidades)} unidades...")
    
    registros_creados = 0
    for u in unidades:
        # Cruza con el odómetro real de Cloudfleet si existe; si no, asigna una base de flota
        ultimo_ot = db.query(OrdenTrabajo).filter(
            OrdenTrabajo.vehicle_code == u.patente_normalizada,
            OrdenTrabajo.status == "closed"
        ).order_by(OrdenTrabajo.number.desc()).first()
        
        odometro_taller = ultimo_ot.odometer if (ultimo_ot and ultimo_ot.odometer) else random.uniform(80000, 350000)
        
        # Variación de km para distribuir semáforos: OK (70%), ADVERTENCIA (15%), CRÍTICO (15%)
        delta_km = random.choice([
            random.uniform(1000, 8500),   # OK
            random.uniform(1000, 8500),
            random.uniform(9100, 9900),   # Próximo a vencer
            random.uniform(10100, 14000)  # Vencido
        ])
        
        odometro_gps = odometro_taller + delta_km
        lat_base, lon_base = random.choice(PUNTOS_RUTA)
        
        nueva_lectura = RegistroTelemetria(
            unidad_id=u.id,
            odometro_gps=round(odometro_gps, 1),
            latitud=round(lat_base + random.uniform(-0.04, 0.04), 4),
            longitud=round(lon_base + random.uniform(-0.04, 0.04), 4),
            velocidad=float(random.choice([0, 0, 42, 68, 82])),
            fuente="Maxtracker_Sim",
            fecha_lectura=datetime.now(timezone.utc)
        )
        db.add(nueva_lectura)
        registros_creados += 1

    db.commit()
    db.close()
    print(f"[SIMULADOR] ✅ {registros_creados} lecturas GPS inyectadas con éxito.")

if __name__ == "__main__":
    simular_telemetria_masiva()