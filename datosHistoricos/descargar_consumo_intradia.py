import requests
import mysql.connector
import json
import time
from datetime import datetime, timedelta

# --- CONFIGURACIÓN ---
USER = "absch"
PASS = "Unvime24"
PLANT_ID = "2613959"
INVERTER_SN = "JNK1CHE00V"

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "datos" 
}

def get_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    })
    login_url = "https://server.growatt.com/login"
    data = {"account": USER, "password": PASS, "validateCode": ""}
    try:
        session.post(login_url, data=data, timeout=10)
        return session
    except Exception as e:
        print(f"Error de sesión: {e}")
        return None

def save_to_db(fecha_hora, consumo):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        consumo_limpio = round(float(consumo), 2)
        query = "REPLACE INTO growatt_consumo_intradia (fecha_hora, consumo_w) VALUES (%s, %s)"
        cursor.execute(query, (fecha_hora, consumo_limpio))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error en DB para {fecha_hora}: {e}")

def extract_day_load_data(session, target_date_str):
    url = "https://server.growatt.com/panel/storage/getStorageEnergyDayChart"
    
    payload = {
        "plantId": PLANT_ID,
        "storageSn": INVERTER_SN,
        "date": target_date_str
    }
    try:
        response = session.post(url, data=payload, timeout=15)
        res_json = response.json()
        
        if 'obj' in res_json and res_json['obj'] is not None:
            charts = res_json['obj'].get('charts', {})
            # Extraemos explícitamente userLoad
            return charts.get('userLoad', None)
    except Exception as e:
        print(f"Fallo en {target_date_str}: {e}")
    return None

# --- PROCESO DE EXTRACCIÓN DE CONSUMO ---
session = get_session()

if session:
    fecha_inicio = datetime(2026, 7, 20)
    fecha_limite = datetime.now() - timedelta(days=1)
    
    print(f"--- DESCARGA DE CONSUMO DESDE {fecha_inicio.strftime('%Y-%m-%d')} HASTA {fecha_limite.strftime('%Y-%m-%d')} ---")
    
    current_date = fecha_inicio
    while current_date <= fecha_limite:
        date_str = current_date.strftime("%Y-%m-%d")
        print(f"Procesando día: {date_str}...", end=" ")
        
        user_load_list = extract_day_load_data(session, date_str)
        
        if user_load_list and isinstance(user_load_list, list):
            registros_guardados = 0
            total_puntos = len(user_load_list) # Usualmente 288 puntos (cada 5 min)
            intervalo_minutos = 1440 / total_puntos if total_puntos > 0 else 5
            
            for idx, val in enumerate(user_load_list):
                if val is not None:
                    try:
                        valor_consumo = float(val)
                        if valor_consumo >= 0:
                            total_mins = int(idx * intervalo_minutos)
                            horas = total_mins // 60
                            minutos = total_mins % 60
                            if horas < 24:
                                fecha_hora_str = f"{date_str} {str(horas).zfill(2)}:{str(minutos).zfill(2)}:00"
                                save_to_db(fecha_hora_str, valor_consumo)
                                registros_guardados += 1
                    except Exception:
                        continue
            print(f"OK ({registros_guardados} registros guardados)")
        else:
            print("Sin datos.")
        
        current_date += timedelta(days=1)
        time.sleep(1)

    print("\n--- DESCARGA DE CONSUMO FINALIZADA ---")