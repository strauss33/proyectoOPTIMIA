import requests
import mysql.connector
from datetime import datetime

# --- CONFIGURACIÓN ---
LAT = "-33.64451720576176"
LON = "-65.44526071823961"

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "datos" 
}

def get_open_meteo_data(fecha_inicio, fecha_fin):
    # API de archivo histórico
    url = (
        f"https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={LAT}&longitude={LON}&start_date={fecha_inicio}&end_date={fecha_fin}"
        f"&daily=temperature_2m_mean,relative_humidity_2m_mean,shortwave_radiation_sum"
        f"&timezone=America%2FArgentina%2FSan_Luis"
    )
    
    try:
        response = requests.get(url, timeout=30)
        if response.status_code != 200: return None
        return response.json()['daily']
    except Exception as e:
        print(f"[X] Error: {e}")
        return None

def ejecutar_carga_openmeteo():
    inicio = "2024-08-01"
    fin = datetime.now().strftime("%Y-%m-%d") 
    
    daily_data = get_open_meteo_data(inicio, fin)
    if not daily_data: return

    fechas = daily_data['time']
    temps = daily_data['temperature_2m_mean']
    humedades = daily_data['relative_humidity_2m_mean']
    radiaciones = daily_data['shortwave_radiation_sum']

    print(f"[*] Procesando {len(fechas)} días...")
    
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        exitos = 0
        for i in range(len(fechas)):
            fecha = fechas[i]
            t = temps[i]
            h = humedades[i]
            r_original = radiaciones[i] # El valor original viene en MJ/m2
            
            if t is None or h is None or r_original is None:
                continue
            
            # --- AQUÍ ESTÁ EL CAMBIO ---
            # Convertimos r_original (MJ/m2) a kWh/m2 dividiendo por 3.6
            r_convertida = round(r_original / 3.6, 4)
            # ---------------------------
                
            query = """
                REPLACE INTO clima_historico_openmeteo 
                (fecha, temperatura_media, humedad_relativa, radiacion_solar) 
                VALUES (%s, %s, %s, %s)
            """
            # Usamos 'r_convertida' en lugar de 'r_original'
            cursor.execute(query, (fecha, t, h, r_convertida))
            exitos += 1
        
        conn.commit()
        print("-" * 30)
        print(f"[V] ¡PROCESO OPEN-METEO FINALIZADO!")
        print(f"[V] Registros convertidos a kWh/m2 y guardados: {exitos}")
        print("-" * 30)
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"[X] Error durante el guardado: {e}")

if __name__ == "__main__":
    ejecutar_carga_openmeteo()