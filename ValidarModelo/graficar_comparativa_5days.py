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


def obtener_datos_5dias():
  try:
    conn = mysql.connector.connect(**DB_CONFIG)

    # Consulta adaptada a la nueva estructura de la tabla energia_estimada_15min
    query = """
            SELECT 
                e.fecha_hora,
                COALESCE(r.potencia_w, 0) AS potencia_real_w,
                (e.energia_estimada_kwh * 1000 * 4) AS potencia_estimada_w
            FROM energia_estimada_15min e
            LEFT JOIN growatt_produccion_intradia r ON e.fecha_hora = r.fecha_hora
            WHERE e.fecha_hora >= '2026-09-12 00:00:00' 
              AND e.fecha_hora <= '2026-09-16 23:45:00'
            ORDER BY e.fecha_hora ASC;
        """
    df = pd.read_sql(query, conn)
    conn.close()
    return df
  except Exception as e:
    print(f"❌ Error al consultar la base de datos: {e}")
    return None


def graficar_serie_completa(df):
  if df is None or df.empty:
    print("❌ No hay datos para graficar.")
    return

  df["fecha_hora"] = pd.to_datetime(df["fecha_hora"])

  fig, ax = plt.subplots(figsize=(20, 7))

  # Trazar series temporales
  ax.plot(
      df["fecha_hora"],
      df["potencia_real_w"],
      label="Potencia Real (Growatt)",
      color="#2ca02c",
      linewidth=1.2,
      marker="o",
      markersize=1.5,
  )
  ax.plot(
      df["fecha_hora"],
      df["potencia_estimada_w"],
      label="Potencia Estimada (Modelo)",
      color="#ff7f0e",
      linewidth=1.2,
      linestyle="--",
  )

  # Escala del Eje X
  ax.xaxis.set_major_locator(mdates.HourLocator(interval=6))
  ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m %H:%M"))
  ax.xaxis.set_minor_locator(mdates.MinuteLocator(interval=15))

  # Formato visual y etiquetas
  plt.title(
      "Comparación Intradía 15 min (5 Días Completos): Real vs Estimada (12/09"
      " al 16/09)",
      fontsize=14,
      fontweight="bold",
  )
  plt.xlabel("Fecha y Hora (Intervalos de 15 min)", fontsize=12)
  plt.ylabel("Potencia (W)", fontsize=12)

  plt.grid(True, which="major", color="#cccccc", linestyle="-", alpha=0.8)
  plt.grid(True, which="minor", color="#eeeeee", linestyle=":", alpha=0.5)
  plt.legend(loc="upper right", fontsize=11)

  plt.xticks(rotation=45)
  plt.tight_layout()

  plt.savefig("comparativa_5_dias_15min.png", dpi=300)
  print("✅ Gráfico guardado como 'comparativa_5_dias_15min.png'")
  plt.show()


if __name__ == "__main__":
  df_datos = obtener_datos_5dias()
  graficar_serie_completa(df_datos)