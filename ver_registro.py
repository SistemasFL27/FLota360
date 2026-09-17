from database import SessionLocal
from models import Unidad

db = SessionLocal()
unidades = db.query(Unidad).all()

print(f"\n--- TOTAL UNIDADES REGISTRADAS: {len(unidades)} ---")
for u in unidades[:10]:  # Muestra las primeras 10
    print(f"UUID: {u.id} | Patente: {u.patente_normalizada} | Cloudfleet ID: {u.cloudfleet_id}")

db.close()