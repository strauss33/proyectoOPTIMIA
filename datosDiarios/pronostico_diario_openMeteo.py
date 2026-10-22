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

def obtener_pronostico():
    # URL de Open-Meteo
    url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&daily=temperature_2m_max,relative_humidity_2m_max,shortwave_radiation_sum&timezone=America%2FArgentina%2FSan_Luis"
    
    try:
        response = requests.get(url)
        if response.status_code != 200:
            print(f"[X] Error API Open-Meteo: {response.status_code}")
            return
        
        data = response.json()
        fecha_consulta = datetime.now().strftime("%Y-%m-%d")
        
        dias = data['daily']['time']
        temps = data['daily']['temperature_2m_max']
        hums = data['daily']['relative_humidity_2m_max']
        rads_mj = data['daily']['shortwave_radiation_sum'] # Viene en MJ/m²
        
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        print(f"[*] Procesando y convirtiendo datos de Open-Meteo...")
        
        for i in range(len(dias)):
            fecha_p = dias[i]
            t = temps[i]
            h = hums[i]
            
            # --- CONVERSIÓN DE UNIDADES ---
            # Dividimos por 3.6 para pasar de MJ/m² a kWh/m²
            # Usamos round(valor, 2) para que no guarde mil decimales
            rad_kwh = round(rads_mj[i] / 3.6, 2)
            
            query = """REPLACE INTO clima_pronosticado 
                       (fecha_consulta, fecha_pronosticada, temp_predicha, humedad_relativa_predicha, radiacion_predicha) 
                       VALUES (%s, %s, %s, %s, %s)"""
            
            cursor.execute(query, (fecha_consulta, fecha_p, t, h, rad_kwh))
        
        conn.commit()
        cursor.close()
        conn.close()
        print(f"[V] Pronóstico guardado en kWh/m² (Conversión: MJ / 3.6).")

    except Exception as e:
        print(f"[X] Error en script de pronóstico: {e}")

if __name__ == "__main__":
    obtener_pronostico()