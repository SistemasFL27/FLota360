import os
import glob
import re
import pandas as pd
from datetime import datetime, timezone
from database import engine, SessionLocal, Base
from models import Unidad, RegistroTelemetria

CARPETA_REPORTES = r"G:\.shortcut-targets-by-id\10KsmDf4qyVGBDbHMLkUwB9jqdDb6ouhG\Compartida Combustible\Promedios general\Promedios 2026"
PATRON_BUSQUEDA = "*Promedios*.xlsx"

def normalizar_patente(patente) -> str:
    if pd.isna(patente):
        return ""
    return re.sub(r'[^A-Z0-9]', '', str(patente).upper())

def limpiar_numero(val):
    if pd.isna(val) or val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).strip()
    if not val_str:
        return None
    if ',' in val_str and '.' in val_str:
        val_str = val_str.replace('.', '').replace(',', '.')
    elif ',' in val_str:
        val_str = val_str.replace(',', '.')
    try:
        return float(val_str)
    except ValueError:
        return None

def importar_telemetria_ypf(origen: str = CARPETA_REPORTES):
    Base.metadata.create_all(bind=engine)
    
    # Filtrar archivos descartando temporales que empiezan con '~$ '
    todos_los_archivos = glob.glob(os.path.join(origen, PATRON_BUSQUEDA))
    archivos = [f for f in todos_los_archivos if not os.path.basename(f).startswith('~$')]

    if not archivos:
        print(f"[EXCEL IMPORT] ❌ No se encontró ninguna planilla válida en: {origen}")
        return

    archivo_final = max(archivos, key=os.path.getmtime)
    print(f"[EXCEL IMPORT] 📄 Procesando desde Drive: {os.path.basename(archivo_final)}")
    excel = pd.ExcelFile(archivo_final)
    db = SessionLocal()

    db.query(RegistroTelemetria).delete()
    db.commit()

    odometros_totales = {}
    hojas_odometro = [h for h in excel.sheet_names if 'YER' in h or 'MonteDual' in h or 'Satelital' in h]
    for hoja in hojas_odometro:
        try:
            df_h = pd.read_excel(excel, sheet_name=hoja)
            df_h.columns = [str(c).strip() for c in df_h.columns]
            col_p = next((c for c in df_h.columns if c.upper() in ['PATENTE', 'PATENTES']), None)
            col_odo = next((c for c in df_h.columns if c.upper() in ['ODOMETRO', 'KILOMETRAJE', 'KILOMETROS']), None)
            if col_p and col_odo:
                for _, row in df_h.iterrows():
                    pat = normalizar_patente(row.get(col_p))
                    num_odo = limpiar_numero(row.get(col_odo))
                    if pat and num_odo is not None and num_odo > 0:
                        odometros_totales[pat] = max(odometros_totales.get(pat, 0.0), num_odo)
        except Exception:
            continue

    meses_orden = ['Diciembre', 'Noviembre', 'Octubre', 'Septiembre', 'Agosto', 'Julio', 'Junio', 'Mayo', 'Abril', 'Marzo', 'Febrero', 'Enero']
    hoja_mes = next((m for m in meses_orden if m in excel.sheet_names), None)

    registros_insertados = 0
    if hoja_mes:
        df_mes = pd.read_excel(excel, sheet_name=hoja_mes)
        df_mes.columns = [str(c).strip() for c in df_mes.columns]

        col_patente = next((c for c in df_mes.columns if c.upper() in ['PATENTE', 'PATENTES']), None)
        col_km_mes = next((c for c in df_mes.columns if 'KM' in c.upper() or 'KILOMETRO' in c.upper()), None)
        col_prom = next((c for c in df_mes.columns if 'PROMEDIO' in c.upper()), None)
        
        # Buscar todas las columnas que contengan "LITRO" o "LTS"
        cols_litros = [c for c in df_mes.columns if 'LITRO' in c.upper() or 'LTS' in c.upper()]

        for _, fila in df_mes.iterrows():
            patente = normalizar_patente(fila.get(col_patente))
            km_mes_num = limpiar_numero(fila.get(col_km_mes))
            prom_num = limpiar_numero(fila.get(col_prom))
            
            # Sumar litros de todas las columnas encontradas
            total_litros = 0.0
            for col in cols_litros:
                val_litro = limpiar_numero(fila.get(col))
                if val_litro is not None:
                    total_litros += val_litro

            if not patente or km_mes_num is None:
                continue

            unidad = db.query(Unidad).filter(Unidad.patente_normalizada == patente).first()
            if not unidad:
                unidad = Unidad(patente_normalizada=patente)
                db.add(unidad)
                db.commit()
                db.refresh(unidad)

            odo_acumulado = odometros_totales.get(patente, None)

            db.add(RegistroTelemetria(
                unidad_id=unidad.id,
                odometro_gps=round(odo_acumulado, 1) if odo_acumulado else None,
                km_recorridos_mes=round(km_mes_num, 1),
                consumo_l100km=round(prom_num, 1) if (prom_num and prom_num > 0) else None,
                litros_combustible=round(total_litros, 1) if total_litros > 0 else None,
                fuente=f"Excel_{hoja_mes}",
                fecha_lectura=datetime.now(timezone.utc)
            ))
            registros_insertados += 1

    db.commit()
    db.close()
    print(f"[EXCEL IMPORT] ✅ {registros_insertados} registros procesados sumando todas las estaciones.")

if __name__ == "__main__":
    importar_telemetria_ypf()