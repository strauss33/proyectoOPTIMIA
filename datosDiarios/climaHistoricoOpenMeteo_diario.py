import requests
import mysql.connector
from datetime import datetime, timedelta

# --- CONFIGURACIÓN ---
LAT = "-33.64451720576176"
LON = "-65.44526071823961"

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "datos" 
}

def actualizar_clima_openmeteo_diario():
    # 1. Definimos la ventana de revisión: últimos 30 días
    # Open-Meteo requiere formato YYYY-MM-DD
    fecha_inicio = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    fecha_fin = datetime.now().strftime("%Y-%m-%d")
    
    # URL de la API Archive (Históricos)
    url = (
        f"https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={LAT}&longitude={LON}&start_date={fecha_inicio}&end_date={fecha_fin}"
        f"&daily=temperature_2m_mean,relative_humidity_2m_mean,shortwave_radiation_sum"
        f"&timezone=America%2FArgentina%2FSan_Luis"
    )
    
    print(f"[*] Revisando Open-Meteo: del {fecha_inicio} al {fecha_fin}...")
    
    try:
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            print(f"[X] Error API Open-Meteo: {response.status_code}")
            return
        
        data = response.json()
        daily = data['daily']
        
        fechas = daily['time']
        temps = daily['temperature_2m_mean']
        hums = daily['relative_humidity_2m_mean']
        rads_mj = daily['shortwave_radiation_sum'] # Viene en MJ/m2
        
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        actualizados = 0

        # Recorremos los datos por índice
        for i in range(len(fechas)):
            f_db = fechas[i]
            t = temps[i]
            h = hums[i]
            r_mj = rads_mj[i]
            
            # FILTRO: Solo guardamos si no hay valores nulos (None)
            if t is not None and h is not None and r_mj is not None:
                
                # CONVERSIÓN: De MJ/m2 a kWh/m2 (dividir por 3.6)
                r_kwh = round(r_mj / 3.6, 4)
                
                query = """
                    REPLACE INTO clima_historico_openmeteo 
                    (fecha, temperatura_media, humedad_relativa, radiacion_solar) 
                    VALUES (%s, %s, %s, %s)
                """
                cursor.execute(query, (f_db, t, h, r_kwh))
                actualizados += 1

        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"[V] Open-Meteo: Se revisaron los últimos 30 días. {actualizados} días actualizados en kWh/m2.")

    except Exception as e:
        print(f"[X] Error en actualización de Open-Meteo: {e}")

if __name__ == "__main__":
    actualizar_clima_openmeteo_diario()