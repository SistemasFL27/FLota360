import os
import glob
import re
import pandas as pd
from datetime import datetime, timezone
from sqlalchemy import text
from database import engine, SessionLocal, Base
import models
from conector_cloudfleet import sincronizar_cloudfleet

CARPETA_REPORTES = r"G:\.shortcut-targets-by-id\10KsmDf4qyVGBDbHMLkUwB9jqdDb6ouhG\Compartida Combustible\Promedios general\Promedios 2026"
PATRON_BUSQUEDA = "Promedios final*.xlsx"

def diagnosticar_y_cargar():
    print("1. Verificando estructura de base de datos...")
    Base.metadata.create_all(bind=engine)
    
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE registro_telemetria ADD COLUMN consumo_l100km FLOAT;"))
            conn.commit()
        except Exception:
            pass

    print("\n2. Sincronizando Mantenimiento desde Cloudfleet...")
    try:
        sincronizar_cloudfleet()
        print("   ✅ Órdenes de trabajo de Cloudfleet actualizadas.")
    except Exception as e:
        print(f"   ⚠️ Cloudfleet no pudo responder: {e}")

    print("\n3. Sincronizando Telemetría/Combustible desde Excel...")
    patron = os.path.join(CARPETA_REPORTES, PATRON_BUSQUEDA)
    archivos = glob.glob(patron)
    if not archivos:
        print(f"   ❌ No se encontró archivo Excel en {CARPETA_REPORTES}")
        return

    archivo_mas_nuevo = max(archivos, key=os.path.getmtime)
    print(f"   Reading: {os.path.basename(archivo_mas_nuevo)}")

    excel = pd.ExcelFile(archivo_mas_nuevo)
    meses_orden = ['Diciembre', 'Noviembre', 'Octubre', 'Septiembre', 'Agosto', 'Julio', 'Junio', 'Mayo', 'Abril', 'Marzo', 'Febrero', 'Enero']
    hoja_mes = next((m for m in meses_orden if m in excel.sheet_names), None)

    if hoja_mes:
        df = pd.read_excel(excel, sheet_name=hoja_mes)
        df.columns = [str(c).strip() for c in df.columns]

        col_patente = next((c for c in df.columns if c.upper() in ['PATENTE', 'PATENTES']), None)
        col_km = next((c for c in df.columns if 'KM' in c.upper() or 'KILOMETRO' in c.upper()), None)
        col_prom = next((c for c in df.columns if 'PROMEDIO' in c.upper()), None)

        db = SessionLocal()
        insertados = 0

        for _, fila in df.iterrows():
            patente_raw = fila.get(col_patente)
            if pd.isna(patente_raw):
                continue

            patente = re.sub(r'[^A-Z0-9]', '', str(patente_raw).upper())
            km_val = fila.get(col_km)
            prom_val = fila.get(col_prom) if col_prom else None

            if not patente or pd.isna(km_val):
                continue

            unidad = db.query(models.Unidad).filter(models.Unidad.patente_normalizada == patente).first()
            if not unidad:
                unidad = models.Unidad(patente_normalizada=patente)
                db.add(unidad)
                db.commit()
                db.refresh(unidad)

            try:
                km_num = float(str(km_val).replace(".", "").replace(",", ".")) if isinstance(km_val, str) else float(km_val)
                prom_num = float(str(prom_val).replace(",", ".")) if pd.notna(prom_val) and str(prom_val).strip() != "" else None

                db.add(models.RegistroTelemetria(
                    unidad_id=unidad.id,
                    odometro_gps=round(km_num, 1),
                    consumo_l100km=round(prom_num, 1) if (prom_num and prom_num > 0) else None,
                    fuente=f"Excel_{hoja_mes}",
                    fecha_lectura=datetime.now(timezone.utc)
                ))
                insertados += 1
            except Exception:
                continue

        db.commit()

    db = SessionLocal()
    total_unidades = db.query(models.Unidad).count()
    total_ots = db.query(models.OrdenTrabajo).count()
    total_telemetria = db.query(models.RegistroTelemetria).count()
    db.close()

    print(f"\n4. ESTADO DE LA BASE DE DATOS:")
    print(f"   ► Unidades totales: {total_unidades}")
    print(f"   ► Órdenes Cloudfleet: {total_ots}")
    print(f"   ► Registros Telemetría: {total_telemetria}")

if __name__ == "__main__":
    diagnosticar_y_cargar()