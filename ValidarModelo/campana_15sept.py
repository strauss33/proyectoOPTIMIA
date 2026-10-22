import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import mysql.connector
import pandas as pd

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "datos",
}


def obtener_datos_dia_especifico(fecha_str="2026-09-15"):
  try:
    conn = mysql.connector.connect(**DB_CONFIG)

    # Filtrar únicamente las 24 horas del día seleccionado (96 intervalos de 15 min)
    query = f"""
            SELECT 
                e.fecha_hora,
                COALESCE(r.potencia_w, 0) AS potencia_real_w,
                (e.energia_estimada_kwh * 1000 * 4) AS potencia_estimada_w
            FROM energia_estimada_15min e
            LEFT JOIN growatt_produccion_intradia r ON e.fecha_hora = r.fecha_hora
            WHERE e.fecha_hora >= '{fecha_str} 00:00:00' 
              AND e.fecha_hora <= '{fecha_str} 23:45:00'
            ORDER BY e.fecha_hora ASC;
        """
    df = pd.read_sql(query, conn)
    conn.close()
    return df
  except Exception as e:
    print(f"❌ Error al consultar la base de datos: {e}")
    return None


def graficar_campana_diaria(df, fecha_str="2026-09-15"):
  if df is None or df.empty:
    print(f"❌ No hay datos registrados para la fecha {fecha_str}.")
    return

  df["fecha_hora"] = pd.to_datetime(df["fecha_hora"])

  fig, ax = plt.subplots(figsize=(14, 6))

  # Graficar las dos campanas
  ax.plot(
      df["fecha_hora"],
      df["potencia_real_w"],
      label="Potencia Real (Growatt)",
      color="#2ca02c",
      linewidth=2.0,
      marker="o",
      markersize=3,
  )
  ax.plot(
      df["fecha_hora"],
      df["potencia_estimada_w"],
      label="Potencia Estimada (Modelo)",
      color="#ff7f0e",
      linewidth=2.0,
      linestyle="--",
  )

  # Formato del eje X (Marcas cada 1 hora de 00:00 a 23:00)
  ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
  ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
  ax.xaxis.set_minor_locator(mdates.MinuteLocator(interval=15))

  # Títulos y marcas visuales
  plt.title(
      f"Campana de Generación Intradía 15 min: {fecha_str}",
      fontsize=14,
      fontweight="bold",
  )
  plt.xlabel("Hora del Día (Intervalos de 15 min)", fontsize=12)
  plt.ylabel("Potencia (W)", fontsize=12)

  # Cuadrícula para medir picos y desfases fácilmente
  plt.grid(True, which="major", color="#cccccc", linestyle="-", alpha=0.8)
  plt.grid(True, which="minor", color="#eeeeee", linestyle=":", alpha=0.5)
  plt.legend(loc="upper right", fontsize=11)

  plt.xticks(rotation=45)
  plt.xlim(df["fecha_hora"].min(), df["fecha_hora"].max())
  plt.tight_layout()

  # Guardar y mostrar
  nombre_archivo = f"campana_generacion_{fecha_str}.png"
  plt.savefig(nombre_archivo, dpi=300)
  print(f"✅ Gráfico guardado como '{nombre_archivo}'")
  plt.show()


if __name__ == "__main__":
  FECHA = "2026-09-15"
  df_dia = obtener_datos_dia_especifico(FECHA)
  graficar_campana_diaria(df_dia, FECHA)