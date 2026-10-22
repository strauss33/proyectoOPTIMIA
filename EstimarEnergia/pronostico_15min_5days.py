from datetime import datetime
import mysql.connector
import pandas as pd
import requests

LAT = "-33.6445"
LON = "-65.4452"
DIAS_PRONOSTICO = 5  # Configurado a 5 días a futuro

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "datos",
}


def obtener_pronostico_15min():
  # URL con forecast_days=5
  url = (
      f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}"
      "&minutely_15=temperature_2m,relative_humidity_2m,surface_pressure,cloud_cover,wind_speed_10m,shortwave_radiation,direct_radiation,diffuse_radiation"
      f"&forecast_days={DIAS_PRONOSTICO}&timezone=America%2FArgentina%2FBuenos_Aires"
  )

  try:
    response = requests.get(url)
    if response.status_code != 200:
      print(f"❌ Error API Open-Meteo: {response.status_code}")
      return

    data = response.json()
    m15 = data["minutely_15"]

    # Crear DataFrame
    df = pd.DataFrame({
        "fecha_hora": m15["time"],
        "temp_c": m15["temperature_2m"],
        "humedad_relativa": m15["relative_humidity_2m"],
        "velocidad_viento": m15["wind_speed_10m"],
        "cobertura_nubes": m15["cloud_cover"],
        "presion_hpa": m15["surface_pressure"],
        "radiacion_global_wm2": m15["shortwave_radiation"],
        "radiacion_directa_wm2": m15["direct_radiation"],
        "radiacion_difusa_wm2": m15["diffuse_radiation"],
    })

    # Formatear fechas y guardar la fecha de la consulta
    df["fecha_hora"] = pd.to_datetime(df["fecha_hora"])
    df["fecha_consulta"] = datetime.now().strftime("%Y-%m-%d")

    # Ordenar columnas
    df_db = df[[
        "fecha_consulta",
        "fecha_hora",
        "temp_c",
        "humedad_relativa",
        "velocidad_viento",
        "cobertura_nubes",
        "presion_hpa",
        "radiacion_global_wm2",
        "radiacion_directa_wm2",
        "radiacion_difusa_wm2",
    ]]

    # Guardar en MySQL
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    query = """
        REPLACE INTO pronostico_15min_5days 
        (fecha_consulta, fecha_hora, temp_c, humedad_relativa, velocidad_viento, cobertura_nubes, presion_hpa, radiacion_global_wm2, radiacion_directa_wm2, radiacion_difusa_wm2) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

    datos_insertar = [tuple(x) for x in df_db.to_numpy()]
    cursor.executemany(query, datos_insertar)

    conn.commit()
    cursor.close()
    conn.close()

    print(
        f"✅ Éxito: Se guardaron {len(df_db)} registros de pronóstico a 15"
        f" minutos para los próximos {DIAS_PRONOSTICO} días."
    )

  except Exception as e:
    print(f"❌ Error en el proceso de pronóstico: {e}")


if __name__ == "__main__":
  obtener_pronostico_15min()