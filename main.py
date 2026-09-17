from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from database import engine, SessionLocal, Base
import models

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Ficha 360 - Dashboard")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/api/tablero-alertas")
def obtener_tablero_alertas(db: Session = Depends(get_db)):
    unidades = db.query(models.Unidad).all()
    resultado = []

    for u in unidades:
        telemetria = db.query(models.RegistroTelemetria)\
            .filter(models.RegistroTelemetria.unidad_id == u.id)\
            .order_by(models.RegistroTelemetria.fecha_lectura.desc()).first()

        ultimo_ot = db.query(models.OrdenTrabajo)\
            .filter(models.OrdenTrabajo.vehicle_code == u.patente_normalizada, models.OrdenTrabajo.status == "closed")\
            .order_by(models.OrdenTrabajo.number.desc()).first()

        km_ot = float(ultimo_ot.odometer) if (ultimo_ot and ultimo_ot.odometer is not None) else 0.0
        
        # Odómetro acumulado total (prefiere la lectura de YPF/GPS, sino la de Cloudfleet)
        km_gps_total = float(telemetria.odometro_gps) if (telemetria and telemetria.odometro_gps) else km_ot
        km_mes = float(telemetria.km_recorridos_mes) if (telemetria and telemetria.km_recorridos_mes) else 0.0
        consumo = float(telemetria.consumo_l100km) if (telemetria and telemetria.consumo_l100km) else None
        fuente = str(telemetria.fuente) if (telemetria and telemetria.fuente) else "Sin Datos"

        delta_km = max(0.0, km_gps_total - km_ot) if (km_gps_total > 0 and km_ot > 0) else 0.0

        if delta_km >= 10000:
            estado = "CRITICO"
        elif delta_km >= 9000:
            estado = "PROXIMO"
        else:
            estado = "OK"

        resultado.append({
            "patente": u.patente_normalizada,
            "km_actuales_gps": round(km_gps_total, 1),
            "km_recorridos_mes": round(km_mes, 1),
            "km_ultimo_service": round(km_ot, 1),
            "km_recorridos_post_service": round(delta_km, 1),
            "consumo_l100km": round(consumo, 1) if consumo else None,
            "estado_semaforo": estado,
            "fuente_gps": fuente
        })

    return resultado

@app.get("/api/unidades/{patente}/ficha-360")
def obtener_ficha_360(patente: str, db: Session = Depends(get_db)):
    patente_clean = patente.upper().replace("-", "").replace(" ", "")
    unidad = db.query(models.Unidad).filter(models.Unidad.patente_normalizada == patente_clean).first()

    if not unidad:
        raise HTTPException(status_code=404, detail="Unidad no encontrada")

    telemetria = db.query(models.RegistroTelemetria)\
        .filter(models.RegistroTelemetria.unidad_id == unidad.id)\
        .order_by(models.RegistroTelemetria.fecha_lectura.desc()).first()

    ultimo_ot = db.query(models.OrdenTrabajo)\
        .filter(models.OrdenTrabajo.vehicle_code == unidad.patente_normalizada, models.OrdenTrabajo.status == "closed")\
        .order_by(models.OrdenTrabajo.number.desc()).first()

    km_ot = float(ultimo_ot.odometer) if (ultimo_ot and ultimo_ot.odometer is not None) else 0.0
    km_gps_total = float(telemetria.odometro_gps) if (telemetria and telemetria.odometro_gps) else km_ot
    km_mes = float(telemetria.km_recorridos_mes) if (telemetria and telemetria.km_recorridos_mes) else 0.0
    consumo = float(telemetria.consumo_l100km) if (telemetria and telemetria.consumo_l100km) else None
    
    # NUEVA LÍNEA: Obtener los litros de combustible
    litros = float(telemetria.litros_combustible) if (telemetria and telemetria.litros_combustible) else None 
    
    fuente = str(telemetria.fuente) if (telemetria and telemetria.fuente) else "Sin Datos"

    delta = max(0.0, km_gps_total - km_ot) if (km_gps_total > 0 and km_ot > 0) else 0.0

    return {
        "patente": unidad.patente_normalizada,
        "mantenimiento": {
            "ultimo_service_km": round(km_ot, 1),
            "km_recorridos": round(delta, 1)
        },
        "telemetria": {
            "odometro_actual": round(km_gps_total, 1),
            "km_recorridos_mes": round(km_mes, 1),
            "consumo_l100km": round(consumo, 1) if consumo else None,
            "litros_mes": round(litros, 1) if litros else None,  # NUEVA LÍNEA: Mandar a la web
            "fuente": fuente
        }
    }

@app.get("/dashboard", response_class=HTMLResponse)
def get_dashboard():
    with open("dashboard.html", "r", encoding="utf-8") as f:
        return f.read()