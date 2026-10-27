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
        # REPLACE actualiza si ya existía el registro de ese horario exacto
        query = "REPLACE INTO growatt_consumo_intradia (fecha_hora, consumo_w) VALUES (%s, %s)"
        cursor.execute(query, (fecha_hora, consumo_limpio))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error en DB para {fecha_hora}: {e}")

def actualizar_dia(session, target_date_str):
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
            user_load_list = charts.get('userLoad', None)
            
            if user_load_list and isinstance(user_load_list, list):
                registros_guardados = 0
                total_puntos = len(user_load_list)
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
                                    fecha_hora_str = f"{target_date_str} {str(horas).zfill(2)}:{str(minutos).zfill(2)}:00"
                                    save_to_db(fecha_hora_str, valor_consumo)
                                    registros_guardados += 1
                        except Exception:
                            continue
                print(f"[{datetime.now()}] ÉXITO: Actualizado consumo del día {target_date_str} ({registros_guardados} registros en W).")
                return True
    except Exception as e:
        print(f"Fallo al actualizar {target_date_str}: {e}")
    return False

# --- FUNCIÓN PRINCIPAL QUE LLAMA EL MAIN ---
def ejecutar_carga_dia_anterior():
    session = get_session()
    if session:
        ayer = datetime.now() - timedelta(days=1)
        ayer_str = ayer.strftime("%Y-%m-%d")
        print(f"Iniciando actualización diaria de consumo intradiario para: {ayer_str}")
        actualizar_dia(session, ayer_str)

# Para poder probar el archivo suelto si lo ejecutás solo
if __name__ == "__main__":
    ejecutar_carga_dia_anterior()