import glob
import os
import pandas as pd

# 1. Pegá acá la ruta de la carpeta donde tenés guardadas las planillas
CARPETA = r"G:\.shortcut-targets-by-id\10KsmDf4qyVGBDbHMLkUwB9jqdDb6ouhG\Compartida Combustible\Promedios general\Promedios 2026"  # Cambiá esta ruta por la carpeta real de tus Excels

patron = os.path.join(CARPETA, "Promedios final*.xlsx")
archivos = glob.glob(patron)

if not archivos:
    print(f"❌ No se encontró ningún archivo 'Promedios final*.xlsx' en la ruta:\n   {CARPETA}\n")
    print("Archivos/carpetas detectados en esa ubicación:")
    if os.path.exists(CARPETA):
        print(os.listdir(CARPETA))
    else:
        print("La ruta especificada no existe.")
    exit()

ultimo_archivo = max(archivos, key=os.path.getmtime)
print(f"📂 Inspeccionando el archivo más reciente: {os.path.basename(ultimo_archivo)}\n")

excel_file = pd.ExcelFile(ultimo_archivo)
print(f"📄 Pestañas encontradas: {excel_file.sheet_names}\n")

for hoja in excel_file.sheet_names:
    df = pd.read_excel(ultimo_archivo, sheet_name=hoja, nrows=2)
    print(f"--- HOJA: '{hoja}' ---")
    print(f"Columnas: {list(df.columns)}")
    print("-" * 60)