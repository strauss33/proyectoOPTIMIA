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

def get_nasa_data(fecha_inicio, fecha_fin):
    url = f"https://power.larc.nasa.gov/api/temporal/daily/point?parameters=T2M,RH2M,ALLSKY_SFC_SW_DWN&community=RE&longitude={LON}&latitude={LAT}&start={fecha_inicio}&end={fecha_fin}&format=JSON"
    
    print(f"[*] Solicitando a NASA: del {fecha_inicio} al {fecha_fin}...")
    try:
        # Aumentamos el timeout porque pediremos muchos datos juntos
        response = requests.get(url, timeout=60)
        if response.status_code != 200:
            print(f"[X] Error de la NASA: {response.status_code}")
            return {}, {}, {}

        data = response.json()
        params = data['properties']['parameter']
        return params['T2M'], params['RH2M'], params['ALLSKY_SFC_SW_DWN']
    except Exception as e:
        print(f"[X] Error de conexión: {e}")
        return {}, {}, {}

def ejecutar_carga_completa():
    # RANGO TOTAL: Desde agosto 2024 hasta hoy
    inicio = "20240801"
    fin = datetime.now().strftime("%Y%m%d") 
    
    t_dict, h_dict, r_dict = get_nasa_data(inicio, fin)
    
    if not t_dict:
        print("[X] No se pudieron obtener datos. Revisa tu conexión.")
        return

    print(f"[*] Procesando {len(t_dict)} días...")
    
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        exitos = 0
        for fecha_str, temp in t_dict.items():
            # Filtro para saltar los días que aún no tienen datos (-999)
            if temp <= -900:
                continue
                
            fecha_db = datetime.strptime(fecha_str, "%Y%m%d").strftime("%Y-%m-%d")
            hum = h_dict[fecha_str]
            rad = r_dict[fecha_str]
            
            query = "REPLACE INTO clima_historico_nasa (fecha, temperatura_media, humedad_relativa, radiacion_solar) VALUES (%s, %s, %s, %s)"
            cursor.execute(query, (fecha_db, temp, hum, rad))
            exitos += 1
        
        conn.commit()
        print(f"---" * 10)
        print(f"[V] ¡PROCESO FINALIZADO!")
        print(f"[V] Registros actualizados/insertados: {exitos}")
        print(f"---" * 10)
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"[X] Error durante el guardado: {e}")

if __name__ == "__main__":
    ejecutar_carga_completa()