from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from database import engine, SessionLocal, Base, ensure_columns
import models
from conector_ypf_ruta import actualizar_gps_odometros, estado_configuracion, sincronizar_ypf_ruta

Base.metadata.create_all(bind=engine)
ensure_columns()

app = FastAPI(title="Ficha 360 - Dashboard")
DASHBOARD_PATH = Path(__file__).resolve().parent / "dashboard.html"
MAPA_PATH = Path(__file__).resolve().parent / "mapa.html"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def get_dashboard():
    return DASHBOARD_PATH.read_text(encoding="utf-8")


@app.get("/mapa", response_class=HTMLResponse)
def get_mapa():
    return MAPA_PATH.read_text(encoding="utf-8")


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "FLota360"}


@app.get("/api/ypf/estado")
def ypf_estado():
    return estado_configuracion()


@app.post("/api/sincronizar-ypf")
def sincronizar_ypf():
    estado = estado_configuracion()
    if not estado["configurado"]:
        raise HTTPException(
            status_code=400,
            detail="Faltan credenciales en .env: " + ", ".join(estado["faltantes"]),
        )
    try:
        return sincronizar_ypf_ruta()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/sincronizar-ypf-gps")
def sincronizar_ypf_gps():
    estado = estado_configuracion()
    if not estado["configurado"]:
        raise HTTPException(
            status_code=400,
            detail="Faltan credenciales en .env: " + ", ".join(estado["faltantes"]),
        )
    try:
        return actualizar_gps_odometros()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/tablero-alertas")
def obtener_tablero_alertas(db: Session = Depends(get_db)):
    unidades = db.query(models.Unidad).all()
    resultado = []

    for u in unidades:
        telemetria = (
            db.query(models.RegistroTelemetria)
            .filter(models.RegistroTelemetria.unidad_id == u.id)
            .order_by(models.RegistroTelemetria.fecha_lectura.desc())
            .first()
        )

        ultimo_ot = (
            db.query(models.OrdenTrabajo)
            .filter(
                models.OrdenTrabajo.vehicle_code == u.patente_normalizada,
                models.OrdenTrabajo.status == "closed",
            )
            .order_by(models.OrdenTrabajo.number.desc())
            .first()
        )

        km_ot = float(ultimo_ot.odometer) if (ultimo_ot and ultimo_ot.odometer is not None) else 0.0
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
            "marca": u.marca,
            "modelo": u.modelo,
            "empresa": u.empresa,
            "km_actuales_gps": round(km_gps_total, 1),
            "km_recorridos_mes": round(km_mes, 1),
            "km_ultimo_service": round(km_ot, 1),
            "km_recorridos_post_service": round(delta_km, 1),
            "consumo_l100km": round(consumo, 1) if consumo else None,
            "estado_semaforo": estado,
            "fuente_gps": fuente,
            "latitud": telemetria.latitud if telemetria else None,
            "longitud": telemetria.longitud if telemetria else None,
            "fecha_lectura": telemetria.fecha_lectura.isoformat() if telemetria and telemetria.fecha_lectura else None,
        })

    return resultado


@app.get("/api/unidades/{patente}/ficha-360")
def obtener_ficha_360(patente: str, db: Session = Depends(get_db)):
    patente_clean = patente.upper().replace("-", "").replace(" ", "")
    unidad = db.query(models.Unidad).filter(models.Unidad.patente_normalizada == patente_clean).first()

    if not unidad:
        raise HTTPException(status_code=404, detail="Unidad no encontrada")

    telemetria = (
        db.query(models.RegistroTelemetria)
        .filter(models.RegistroTelemetria.unidad_id == unidad.id)
        .order_by(models.RegistroTelemetria.fecha_lectura.desc())
        .first()
    )

    ultimo_ot = (
        db.query(models.OrdenTrabajo)
        .filter(
            models.OrdenTrabajo.vehicle_code == unidad.patente_normalizada,
            models.OrdenTrabajo.status == "closed",
        )
        .order_by(models.OrdenTrabajo.number.desc())
        .first()
    )

    km_ot = float(ultimo_ot.odometer) if (ultimo_ot and ultimo_ot.odometer is not None) else 0.0
    km_gps_total = float(telemetria.odometro_gps) if (telemetria and telemetria.odometro_gps) else km_ot
    km_mes = float(telemetria.km_recorridos_mes) if (telemetria and telemetria.km_recorridos_mes) else 0.0
    consumo = float(telemetria.consumo_l100km) if (telemetria and telemetria.consumo_l100km) else None
    litros = float(telemetria.litros_combustible) if (telemetria and telemetria.litros_combustible) else None
    fuente = str(telemetria.fuente) if (telemetria and telemetria.fuente) else "Sin Datos"
    delta = max(0.0, km_gps_total - km_ot) if (km_gps_total > 0 and km_ot > 0) else 0.0

    return {
        "patente": unidad.patente_normalizada,
        "marca": unidad.marca,
        "modelo": unidad.modelo,
        "empresa": unidad.empresa,
        "mantenimiento": {
            "ultimo_service_km": round(km_ot, 1),
            "km_recorridos": round(delta, 1),
            "orden_numero": ultimo_ot.number if ultimo_ot else None,
            "comentarios": ultimo_ot.comments if ultimo_ot else None,
        },
        "telemetria": {
            "odometro_actual": round(km_gps_total, 1),
            "km_recorridos_mes": round(km_mes, 1),
            "consumo_l100km": round(consumo, 1) if consumo else None,
            "litros_mes": round(litros, 1) if litros else None,
            "fuente": fuente,
            "latitud": telemetria.latitud if telemetria else None,
            "longitud": telemetria.longitud if telemetria else None,
            "fecha_lectura": telemetria.fecha_lectura.isoformat() if telemetria and telemetria.fecha_lectura else None,
        },
        "ypf": {
            "device_id": unidad.ypf_device_id,
            "imei": unidad.ypf_imei,
        },
    }
