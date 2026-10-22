import requests
import mysql.connector
import json
import time
from datetime import datetime, timedelta

# --- CONFIGURACIÓN ---
USER = "absch"
PASS = "Unvime24"
PLANT_ID = "2613959"

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

def save_to_db(fecha, valor):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        valor_limpio = round(float(valor), 2)
        query = "REPLACE INTO growatt_produccion (fecha, energia) VALUES (%s, %s)"
        cursor.execute(query, (fecha, valor_limpio))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error en DB para {fecha}: {e}")

def extract_month_data(session, target_month):
    url = "https://server.growatt.com/energy/compare/getDevicesMonthChart"
    payload = {
        "plantId": PLANT_ID,
        "date": target_month,
        "jsonData": json.dumps([{"type":"plant","sn":PLANT_ID,"params":"energy,autoEnergy"}])
    }
    try:
        response = session.post(url, data=payload, timeout=15)
        res_json = response.json()
        if 'obj' in res_json and len(res_json['obj']) > 0:
            return res_json['obj'][0]['datas'].get('energy', [])
    except Exception as e:
        print(f"Fallo en {target_month}: {e}")
    return None

# --- PROCESO HISTÓRICO ---
session = get_session()

if session:
    meses = [
        "2024-08", "2024-09", "2024-10", "2024-11", "2024-12",
        "2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06",
        "2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12",
        "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06", 
        "2026-07", "2026-08", "2026-09"
    ]

    # Definimos el límite: hasta ayer (8 de abril si hoy es 9)
    # Esto evita que promedie el 9 o el 10 de abril.
    fecha_limite = datetime.now() - timedelta(days=1)
    
    print(f"--- CARGA HISTÓRICA HASTA EL {fecha_limite.strftime('%Y-%m-%d')} ---")
    
    ultimo_valor_mes_anterior = 0.0

    for mes in meses:
        print(f"Procesando: {mes}...", end=" ")
        lista_energia = extract_month_data(session, mes)
        
        if lista_energia:
            huecos_mes = 0
            for i in range(len(lista_energia)):
                dia = i + 1
                fecha_actual = datetime.strptime(f"{mes}-{str(dia).zfill(2)}", "%Y-%m-%d")
                
                # SI LA FECHA ES MAYOR A AYER, SALTAMOS (No procesamos hoy ni el futuro)
                if fecha_actual > fecha_limite:
                    continue

                valor_actual = float(lista_energia[i])
                
                # Lógica de Promedios (solo para días pasados)
                if valor_actual == 0.0:
                    v_anterior = float(lista_energia[i-1]) if i > 0 else ultimo_valor_mes_anterior
                    v_posterior = float(lista_energia[i+1]) if i < len(lista_energia)-1 else 0.0
                    
                    if v_anterior > 0 and v_posterior > 0:
                        valor_actual = (v_anterior + v_posterior) / 2
                        huecos_mes += 1
                    elif v_anterior > 0:
                        valor_actual = v_anterior
                        huecos_mes += 1
                    elif v_posterior > 0:
                        valor_actual = v_posterior
                        huecos_mes += 1

                if valor_actual > 0:
                    save_to_db(fecha_actual.strftime("%Y-%m-%d"), valor_actual)
            
            # Actualizamos el valor para el puente entre meses
            for val in reversed(lista_energia):
                if float(val) > 0:
                    ultimo_valor_mes_anterior = float(val)
                    break
            
            print(f"OK (Huecos: {huecos_mes})")
        
        time.sleep(2)

    print("\n--- CARGA HISTÓRICA FINALIZADA ---")