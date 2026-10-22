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


def calcular_y_comparar_mes():
  try:
    conn = mysql.connector.connect(**DB_CONFIG)

    # Consulta para el mes completo de Septiembre 2026
    query = """
            SELECT 
                c.fecha,
                c.temperatura_media,
                c.humedad_relativa,
                c.radiacion_solar,
                COALESCE(g.energia, 0) AS energia_real_kwh
            FROM clima_historico_openmeteo c
            LEFT JOIN growatt_produccion g ON c.fecha = g.fecha
            WHERE c.fecha >= '2026-09-01' AND c.fecha <= '2026-09-30'
            ORDER BY c.fecha ASC;
        """
    df = pd.read_sql(query, conn)
    conn.close()

    if df.empty:
      print("❌ No se encontraron datos para ese rango.")
      return

    # Parámetros del Modelo Viejo (Simplificado Diario)
    POTENCIA_PICO = 2.25  # kWp
    EFICIENCIA_INV = 0.93  # 93%
    PR_BASE = 0.88
    GAMMA = -0.0035

    # Aplicación de la fórmula diaria
    f_termico = 1 + GAMMA * (df["temperatura_media"] - 25)
    f_humedad = 1 - (0.002 * (df["humedad_relativa"] / 100))
    pr_dinamico_viejo = PR_BASE * f_termico * f_humedad

    df["energia_estimada_vieja"] = (
        df["radiacion_solar"] * POTENCIA_PICO * EFICIENCIA_INV * pr_dinamico_viejo
    ).clip(lower=0)

    # --- GRAFICAR ---
    fig, ax = plt.subplots(figsize=(12, 6))

    df["fecha"] = pd.to_datetime(df["fecha"])

    ax.plot(
        df["fecha"],
        df["energia_real_kwh"],
        label="Energía Real Diaria (Growatt)",
        color="#2ca02c",
        linewidth=1.5,
        marker="o",
    )
    ax.plot(
        df["fecha"],
        df["energia_estimada_vieja"],
        label="Energía Estimada (Modelo Viejo - Diario)",
        color="#d62728",
        linewidth=1.5,
        linestyle="--",
        marker="x",
    )

    # --- AQUÍ ESTÁN LOS CAMBIOS PARA LAS FECHAS ---
    # Intervalo de 2 días para que respire el eje X y rotación de 45°
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m/%Y"))
    plt.xticks(rotation=45, ha="right")
    # ---------------------------------------------

    plt.title(
        "Comparación Mensual (Septiembre 2026): Producción Real vs. Modelo"
        " Viejo",
        fontsize=14,
        fontweight="bold",
    )
    plt.xlabel("Fecha", fontsize=12)
    plt.ylabel("Energía Diaria (kWh)", fontsize=12)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(fontsize=11)
    plt.tight_layout()  # Vital para que el texto rotado no se corte abajo

    plt.savefig("comparativa_modelo_viejo_mes.png", dpi=300)
    print("✅ Gráfico guardado como 'comparativa_modelo_viejo_mes.png'")
    plt.show()

  except Exception as e:
    print(f"❌ Error: {e}")


if __name__ == "__main__":
  calcular_y_comparar_mes()