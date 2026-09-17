import re
from database import engine, SessionLocal, Base
from models import OrdenTrabajo, Unidad

def normalizar_patente(patente: str) -> str:
    """Convierte 'GPV-408', 'gpv 408' o 'gpv408' a 'GPV408'."""
    if not patente:
        return ""
    return re.sub(r'[^A-Z0-9]', '', patente.upper())

def poblar_padron_unidades():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # Extraer patentes únicas de las órdenes de trabajo guardadas
    patentes_raw = db.query(OrdenTrabajo.vehicle_code).distinct().all()
    print(f"Procesando {len(patentes_raw)} patentes únicas encontradas en Cloudfleet...")
    
    unidades_creadas = 0
    for (patente_raw,) in patentes_raw:
        patente_limpia = normalizar_patente(patente_raw)
        if not patente_limpia:
            continue
            
        # Buscar si ya existe la unidad por patente normalizada
        unidad_existente = db.query(Unidad).filter(Unidad.patente_normalizada == patente_limpia).first()
        
        if not unidad_existente:
            nueva_unidad = Unidad(
                patente_normalizada=patente_limpia,
                cloudfleet_id=patente_raw  # ID externo para el cruce de fuentes
            )
            db.add(nueva_unidad)
            unidades_creadas += 1
            print(f"+ Nueva unidad registrada: {patente_limpia} (Cloudfleet ID: {patente_raw})")
    
    db.commit()
    db.close()
    print(f"\n¡Éxito! Se crearon {unidades_creadas} unidades maestras con ID interno (UUID).")

if __name__ == "__main__":
    poblar_padron_unidades()