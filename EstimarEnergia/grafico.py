from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import pandas as pd
from sqlalchemy import create_engine

engine = create_engine("mysql+mysqlconnector://root:@localhost/datos")


def graficar_comparacion_ayer():
  # Definir la fecha del día anterior
  ayer = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
  # O si quieres probar con una fecha específica donde tengas datos guardados:
  # ayer = "2026-09-25"

  print(f"Generando gráfico comparativo para el día: {ayer}")

  # 1. Obtener datos reales de Growatt para ese día
  query_growatt = f"""
        SELECT fecha_hora, potencia_w 
        FROM growatt_produccion_intradia 
        WHERE DATE(fecha_hora) = '{ayer}'
        ORDER BY fecha_hora ASC
    """
  df_growatt = pd.read_sql(query_growatt, engine)

  # 2. Obtener datos estimados/pronosticados para ese día
  query_estimado = f"""
        SELECT fecha_hora, energia_estimada_kwh 
        FROM energia_pronosticada 
        WHERE DATE(fecha_hora) = '{ayer}'
        ORDER BY fecha_hora ASC
    """
  df_estimado = pd.read_sql(query_estimado, engine)

  if df_growatt.empty or df_estimado.empty:
    print(
        f"❌ No hay suficientes datos para comparar en la fecha {ayer}."
    )
    return

  # Convertir fecha_hora a datetime
  df_growatt["fecha_hora"] = pd.to_datetime(df_growatt["fecha_hora"])
  df_estimado["fecha_hora"] = pd.to_datetime(df_estimado["fecha_hora"])

  # Convertir Potencia (W) de Growatt a Energía (kWh) en el intervalo de 15 min
  df_growatt["energia_real_kwh"] = (
      df_growatt["potencia_w"] * 0.25 / 1000.0
  )

  # Unir ambos DataFrames por la fecha_hora
  df_final = pd.merge(
      df_estimado, df_growatt[["fecha_hora", "energia_real_kwh"]], on="fecha_hora", how="inner"
  )

  if df_final.empty:
    print("❌ No se pudieron alinear los registros por hora.")
    return

  # Extraer solo la hora para mostrar en el eje X del gráfico
  df_final["hora_str"] = df_final["fecha_hora"].dt.strftime("%H:%M")

  # 3. Crear el Gráfico
  plt.figure(figsize=(12, 6))

  plt.plot(
      df_final["hora_str"],
      df_final["energia_estimada_kwh"],
      label="Energía Pronosticada (kWh)",
      color="orange",
      linestyle="--",
      marker="o",
      markersize=3,
  )
  plt.plot(
      df_final["hora_str"],
      df_final["energia_real_kwh"],
      label="Energía Real Growatt (kWh)",
      color="green",
      marker="x",
      markersize=4,
  )

  plt.title(
      f"Comparación de Energía: Pronosticada vs Real - {ayer}", fontsize=14
  )
  plt.xlabel("Hora del Día", fontsize=12)
  plt.ylabel("Energía en 15 min (kWh)", fontsize=12)
  plt.xticks(
      rotation=45, ticks=range(0, len(df_final), 4)
  )  # Mostrar etiqueta cada 1 hora (4 * 15 min)
  plt.grid(True, linestyle=":", alpha=0.6)
  plt.legend(fontsize=12)
  plt.tight_layout()

  # Mostrar el gráfico en pantalla
  plt.show()


if __name__ == "__main__":
  graficar_comparacion_ayer()