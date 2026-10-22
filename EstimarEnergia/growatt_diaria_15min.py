from datetime import datetime, timedelta
import json
import time
import requests
import mysql.connector

# --- CONFIGURACIÓN ---
USER = "absch"
PASS = "Unvime24"
PLANT_ID = "2613959"

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "datos",
}


def get_session():
  session = requests.Session()
  session.headers.update({
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
          " like Gecko) Chrome/123.0.0.0 Safari/537.36"
      )
  })
  login_url = "https://server.growatt.com/login"
  data = {"account": USER, "password": PASS, "validateCode": ""}
  try:
    session.post(login_url, data=data, timeout=10)
    return session
  except Exception as e:
    print(f"Error de sesión: {e}")
    return None


# --- GUARDADO EN BASE DE DATOS ---


def save_to_db_intradia(fecha_hora, potencia_w):
  """Guarda lecturas de potencia instantánea (potencia_w) cada 15 min"""
  try:
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    query = """
            REPLACE INTO growatt_produccion_intradia (fecha_hora, potencia_w) 
            VALUES (%s, %s)
        """
    cursor.execute(query, (fecha_hora, round(float(potencia_w), 2)))
    conn.commit()
    cursor.close()
    conn.close()
  except Exception as e:
    print(f"Error en DB para {fecha_hora}: {e}")


# --- EXTRACCIÓN Y PROCESAMIENTO ---


def extract_day_chart_data(session, target_date):
  url = "https://server.growatt.com/energy/compare/getDevicesDayChart"
  payload = {
      "plantId": PLANT_ID,
      "date": target_date,
      "jsonData": json.dumps(
          [{"type": "plant", "sn": PLANT_ID, "params": "pac"}]
      ),
  }
  try:
    response = session.post(url, data=payload, timeout=15)
    res_json = response.json()
    if "obj" in res_json and len(res_json["obj"]) > 0:
      return res_json["obj"][0].get("datas", {})
  except Exception as e:
    print(f"Fallo al extraer datos para {target_date}: {e}")
  return None


def procesar_intradia(session, fecha_str):
  print(
      f"[{datetime.now().strftime('%H:%M:%S')}] Procesando datos del día"
      f" anterior ({fecha_str})..."
  )
  datas = extract_day_chart_data(session, fecha_str)

  if not datas:
    print(f"No se obtuvieron datos para {fecha_str}.")
    return

  pac_list = datas.get("pac", [])
  registros_guardados = 0

  for i, pot in enumerate(pac_list):
    minutos_totales = i * 5  # Growatt devuelve datos cada 5 minutos
    horas = minutos_totales // 60
    mins = minutos_totales % 60

    if horas >= 24:
      break

    # Filtro para guardar únicamente los intervalos de 15 minutos (0, 15, 30, 45)
    if mins not in [0, 15, 30, 45]:
      continue

    timestamp_str = (
        f"{fecha_str} {str(horas).zfill(2)}:{str(mins).zfill(2)}:00"
    )
    pot_val = float(pot) if pot else 0.0

    save_to_db_intradia(timestamp_str, pot_val)
    registros_guardados += 1

  print(
      f"-> Día {fecha_str} procesado exitosamente ({registros_guardados}"
      " registros guardados a 15 min)."
  )


def ejecutar_carga_dia_anterior():
  session = get_session()

  if not session:
    print("No se pudo iniciar sesión en Growatt.")
    return

  # Calcula automáticamente la fecha de ayer
  ayer = datetime.now() - timedelta(days=1)
  fecha_ayer = ayer.strftime("%Y-%m-%d")

  procesar_intradia(session, fecha_ayer)

  print("\n--- PROCESAMIENTO DIARIO FINALIZADO ---")


# --- INICIO ---
if __name__ == "__main__":
  ejecutar_carga_dia_anterior()