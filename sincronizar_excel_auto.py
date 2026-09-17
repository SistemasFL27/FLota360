import os
import glob
from datetime import datetime
from conector_ypf_excel import importar_telemetria_ypf

# Indicá la carpeta donde se guardan las planillas (puedes usar r"." para la carpeta actual)
CARPETA_REPORTES = r"." 
PATRON_BUSQUEDA = "Promedios final*.xlsx"

ULTIMO_ARCHIVO_PROCESADO = None
ULTIMA_FECHA_MODIFICACION = None

def obtener_ultimo_excel():
    """Busca todos los archivos que coincidan con el patrón y devuelve el de fecha más reciente."""
    ruta_patron = os.path.join(CARPETA_REPORTES, PATRON_BUSQUEDA)
    archivos = glob.glob(ruta_patron)
    
    if not archivos:
        return None
    
    # Evalúa la fecha de modificación de cada archivo de la lista y retorna el máximo
    return max(archivos, key=os.path.getmtime)

def verificar_y_actualizar_excel():
    global ULTIMO_ARCHIVO_PROCESADO, ULTIMA_FECHA_MODIFICACION

    archivo_mas_nuevo = obtener_ultimo_excel()

    if not archivo_mas_nuevo:
        print(f"[MONITOR EXCEL] ⚠️ No se encontraron planillas con el patrón '{PATRON_BUSQUEDA}'")
        return

    mtime_actual = os.path.getmtime(archivo_mas_nuevo)

    # Si apareció un archivo nuevo (cambio de mes) o si el archivo actual fue modificado
    if (archivo_mas_nuevo != ULTIMO_ARCHIVO_PROCESADO) or (ULTIMA_FECHA_MODIFICACION is None or mtime_actual > ULTIMA_FECHA_MODIFICACION):
        nombre_archivo = os.path.basename(archivo_mas_nuevo)
        print(f"\n[MONITOR EXCEL] 🔄 Se detectó una nueva versión de reporte:")
        print(f"📄 Archivo seleccionado: {nombre_archivo}")
        print(f"📅 Modificado el: {datetime.fromtimestamp(mtime_actual)}")
        
        try:
            importar_telemetria_ypf(archivo_mas_nuevo)
            ULTIMO_ARCHIVO_PROCESADO = archivo_mas_nuevo
            ULTIMA_FECHA_MODIFICACION = mtime_actual
            print("[MONITOR EXCEL] ✅ Padrón y telemetría actualizados correctamente en el dashboard.")
        except Exception as e:
            print(f"[MONITOR EXCEL] ❌ Error leyendo el archivo: {e}")
    else:
        print("[MONITOR EXCEL] El reporte más reciente no ha sufrido cambios.")

if __name__ == "__main__":
    verificar_y_actualizar_excel()