from sqlalchemy.orm import Session
from models import Unidad, OrdenTrabajo, RegistroTelemetria

# Umbral por defecto para alerta de mantenimiento (ej: 10.000 km entre services)
INTERVALO_SERVICE_KM = 10000 

def generar_ficha_360(patente: str, db: Session) -> dict:
    patente_limpia = patente.upper().replace("-", "").replace(" ", "")
    
    # 1. Buscar unidad en el Padrón Maestro
    unidad = db.query(Unidad).filter(Unidad.patente_normalizada == patente_limpia).first()
    if not unidad:
        return None

    # 2. Último odómetro registrado por GPS
    ultima_telemetria = db.query(RegistroTelemetria).filter(
        RegistroTelemetria.unidad_id == unidad.id
    ).order_by(RegistroTelemetria.fecha_lectura.desc()).first()

    # 3. Último mantenimiento cerrado en Cloudfleet
    ultimo_mantenimiento = db.query(OrdenTrabajo).filter(
        OrdenTrabajo.vehicle_code == patente_limpia,
        OrdenTrabajo.status == "closed"
    ).order_by(OrdenTrabajo.number.desc()).first()

    odometro_gps = ultima_telemetria.odometro_gps if ultima_telemetria else 0.0
    odometro_taller = ultimo_mantenimiento.odometer if (ultimo_mantenimiento and ultimo_mantenimiento.odometer) else 0.0

    # 4. Cálculo de diferencia y evaluación de alertas
    km_recorridos_post_service = max(0.0, odometro_gps - odometro_taller)
    
    if odometro_gps == 0.0:
        estado_alerta = "SIN_DATOS_GPS"
    elif km_recorridos_post_service >= INTERVALO_SERVICE_KM:
        estado_alerta = "CRITICO_SERVICE_VENCIDO"
    elif km_recorridos_post_service >= (INTERVALO_SERVICE_KM - 1000):
        estado_alerta = "ADVERTENCIA_SERVICE_PROXIMO"
    else:
        estado_alerta = "OK"

    return {
        "uuid": unidad.id,
        "patente": patente_limpia,
        "estado_alerta": estado_alerta,
        "kilometraje": {
            "actual_gps": odometro_gps,
            "ultimo_service_taller": odometro_taller,
            "km_recorridos_desde_ultimo_service": km_recorridos_post_service,
            "km_restantes_para_service": max(0.0, INTERVALO_SERVICE_KM - km_recorridos_post_service)
        },
        "ultimo_mantenimiento": {
            "orden_numero": ultimo_mantenimiento.number if ultimo_mantenimiento else None,
            "comentarios": ultimo_mantenimiento.comments if ultimo_mantenimiento else None
        } if ultimo_mantenimiento else None,
        "ultima_posicion_gps": {
            "latitud": ultima_telemetria.latitud if ultima_telemetria else None,
            "longitud": ultima_telemetria.longitud if ultima_telemetria else None,
            "fecha": ultima_telemetria.fecha_lectura if ultima_telemetria else None
        } if ultima_telemetria else None
    }
def generar_tablero_alertas(db: Session) -> dict:
    unidades = db.query(Unidad).all()
    
    resumen = {
        "total_unidades": len(unidades),
        "criticos": 0,
        "advertencias": 0,
        "ok": 0,
        "sin_datos_gps": 0
    }
    
    detalle_unidades = []
    
    for u in unidades:
        ficha = generar_ficha_360(u.patente_normalizada, db)
        if not ficha:
            continue
            
        estado = ficha["estado_alerta"]
        
        if estado == "CRITICO_SERVICE_VENCIDO":
            resumen["criticos"] += 1
        elif estado == "ADVERTENCIA_SERVICE_PROXIMO":
            resumen["advertencias"] += 1
        elif estado == "OK":
            resumen["ok"] += 1
        else:
            resumen["sin_datos_gps"] += 1
            
        detalle_unidades.append({
            "uuid": ficha["uuid"],
            "patente": ficha["patente"],
            "estado_alerta": estado,
            "km_actuales_gps": ficha["kilometraje"]["actual_gps"],
            "km_recorridos_post_service": ficha["kilometraje"]["km_recorridos_desde_ultimo_service"],
            "km_restantes": ficha["kilometraje"]["km_restantes_para_service"]
        })
        
    return {
        "resumen_ejecutivo": resumen,
        "unidades": detalle_unidades
    }