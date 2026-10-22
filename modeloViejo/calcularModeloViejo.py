import matplotlib.pyplot as plt
import mysql.connector
import pandas as pd

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "datos",
}


def calcular_y_comparar_modelo_viejo():
  try:
    conn = mysql.connector.connect(**DB_CONFIG)

    # Consulta que une el clima diario con la producción real diaria de Growatt
    query = """
            SELECT 
                c.fecha,
                c.temperatura_media,
                c.humedad_relativa,
                c.radiacion_solar,
                COALESCE(g.energia, 0) AS energia_real_kwh
            FROM clima_historico_openmeteo c
            LEFT JOIN growatt_produccion g ON c.fecha = g.fecha
            WHERE c.fecha >= '2024-08-01' AND c.fecha <= CURDATE()
            ORDER BY c.fecha ASC;
        """
    df = pd.read_sql(query, conn)
    conn.close()

    if df.empty:
      print("❌ No se encontraron datos.")
      return

    # Parámetros del Modelo Viejo (Simplificado Diario)
    POTENCIA_PICO = 2.25  # kWp
    EFICIENCIA_INV = 0.93  # 93%
    PR_BASE = 0.88  # Factor de rendimiento fijo antiguo
    GAMMA = -0.0035  # Coeficiente térmico

    # Aplicación de la fórmula simplificada diaria
    # Nota: Como la radiación ya viene en kWh/m² (equivalente a horas solares pico diarias),
    # se multiplica directamente por la potencia pico sin factor horario adicional.
    f_termico = 1 + GAMMA * (df["temperatura_media"] - 25)
    f_humedad = 1 - (0.002 * (df["humedad_relativa"] / 100))
    pr_dinamico_viejo = PR_BASE * f_termico * f_humedad

    df["energia_estimada_vieja"] = (
        df["radiacion_solar"] * POTENCIA_PICO * EFICIENCIA_INV * pr_dinamico_viejo
    ).clip(lower=0)

    # --- GRAFICAR COMPARATIVA ---
    plt.figure(figsize=(15, 6))

    plt.plot(
        pd.to_datetime(df["fecha"]),
        df["energia_real_kwh"],
        label="Energía Real (Growatt)",
        color="#2ca02c",
        linewidth=1.5,
    )
    plt.plot(
        pd.to_datetime(df["fecha"]),
        df["energia_estimada_vieja"],
        label="Energía Estimada (Modelo Viejo - Diario)",
        color="#d62728",
        linewidth=1.2,
        linestyle="--",
    )

    plt.title(
        "Validación Histórica: Producción Real vs. Modelo Viejo (Resolución"
        " Diaria)",
        fontsize=14,
        fontweight="bold",
    )
    plt.xlabel("Fecha", fontsize=12)
    plt.ylabel("Energía Diaria (kWh)", fontsize=12)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(fontsize=11)
    plt.tight_layout()

    plt.savefig("comparativa_modelo_viejo_diario.png", dpi=300)
    print("✅ Gráfico guardado como 'comparativa_modelo_viejo_diario.png'")
    plt.show()

  except Exception as e:
    print(f"❌ Error: {e}")


if __name__ == "__main__":
  calcular_y_comparar_modelo_viejo()