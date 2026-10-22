import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text

# --- PARÁMETROS TÉCNICOS SEGÚN DATASHEET Y MODELO FÍSICO ---
POTENCIA_PICO_TOTAL = 2.25   # 5 paneles x 450W (kWp)
EFICIENCIA_INV = 0.93        # Inversor Growatt (93%)
PR_BASE = 0.78               # Pérdidas fijas (cables, suciedad, desacople)
GAMMA = -0.0035              # Coeficiente térmico de potencia (-0.35%/°C)
NOCT = 45.0                  # Normal Operating Cell Temperature (°C)
INCLINACION_PANEL = 35.0     # Ángulo de inclinación (grados)
FACTOR_15MIN = 0.25          # 15 minutos equivalen a 0.25 horas

engine = create_engine("mysql+mysqlconnector://root:@localhost/datos")

def cargar_energia_estimada_15min():
    try:
        # 1. Extracción de datos meteorológicos a resolución de 15 Minutos
        query = """
        SELECT 
            fecha_hora,
            DATE(fecha_hora) AS fecha,
            TIME(fecha_hora) AS hora,
            temperatura AS temp,
            humedad_relativa AS hum,
            radiacion_solar AS rad_global, -- Irradiancia instantánea en W/m² o kW/m²
            COALESCE(velocidad_viento, 2.0) AS viento,
            COALESCE(cobertura_nubes, 20.0) AS nubes,
            COALESCE(presion_superficie, 1013.25) AS presion,
            COALESCE(radiacion_directa, radiacion_solar * 0.7) AS rad_directa,
            COALESCE(radiacion_difusa, radiacion_solar * 0.3) AS rad_difusa
        FROM clima_15min_openmeteo
        WHERE fecha_hora >= '2024-08-01 00:00:00' AND fecha_hora <= NOW()
        ORDER BY fecha_hora ASC
        """
        df = pd.read_sql(query, engine)

        if df.empty:
            print("❌ No se encontraron datos en 'clima_15min_openmeteo'.")
            return

        # Convertir W/m² a kW/m² si la fuente viene en W/m²
        # Si ya viene en kW/m², puedes omitir la división por 1000
        if df['rad_global'].max() > 10:
            df['rad_global'] /= 1000.0
            df['rad_directa'] /= 1000.0
            df['rad_difusa'] /= 1000.0

        # 2. Corrección de Irradiancia Efectiva según Inclinación a 35°
        rad_tilt_factor = 1.0 + (0.18 * np.sin(np.radians(INCLINACION_PANEL)))
        df['rad_efectiva'] = df['rad_directa'] * rad_tilt_factor + df['rad_difusa']

        # 3. Modelo Térmico Dinámico a 15 Minutos
        factor_viento = np.exp(-0.05 * df['viento'])
        # Ajuste de temperatura de célula en la ventana de 15 min
        df['t_cell'] = df['temp'] + ((df['rad_global'] / 0.8) * (NOCT - 20) / 800) * factor_viento
        df['f_termico'] = 1 + GAMMA * (df['t_cell'] - 25)

        # 4. Atenuaciones Ambientales
        df['f_humedad'] = 1 - (0.002 * (df['hum'] / 100))
        df['f_presion'] = 1 + 0.00005 * (df['presion'] - 1013.25)
        df['f_nubes'] = 1 - (0.0005 * df['nubes'])

        # 5. Performance Ratio (PR) Dinámico en la ventana de 15 min
        df['pr_dinamico'] = PR_BASE * df['f_termico'] * df['f_humedad'] * df['f_presion'] * df['f_nubes']

        # 6. Cálculo final de la energía generada en el intervalo de 15 minutos (kWh)
        # Se incluye FACTOR_15MIN (0.25 h) para convertir Potencia (kW) en Energía (kWh)
        df['energia_estimada_kwh'] = np.where(
            df['rad_efectiva'] > 0,
            (df['rad_efectiva'] * POTENCIA_PICO_TOTAL * EFICIENCIA_INV * df['pr_dinamico'] * FACTOR_15MIN).round(4),
            0.0
        )

        # 7. Formateo de columnas para la BD
        df_db = df[[
            'fecha_hora', 'fecha', 'hora', 'temp', 'hum', 'viento', 
            'nubes', 'presion', 'rad_efectiva', 'energia_estimada_kwh'
        ]].copy()

        df_db.columns = [
            'fecha_hora', 'fecha', 'hora', 'temp_c', 'humedad_relativa', 
            'velocidad_viento', 'cobertura_nubes', 'presion_hpa', 
            'radiacion_inclinada_kwhm2', 'energia_estimada_kwh'
        ]

        # 8. Guardado en la Base de Datos
        with engine.begin() as connection:
            connection.execute(text("""
            CREATE TABLE IF NOT EXISTS energia_estimada_15min (
                fecha_hora DATETIME PRIMARY KEY,
                fecha DATE,
                hora TIME,
                temp_c FLOAT,
                humedad_relativa FLOAT,
                velocidad_viento FLOAT,
                cobertura_nubes FLOAT,
                presion_hpa FLOAT,
                radiacion_inclinada_kwhm2 FLOAT,
                energia_estimada_kwh FLOAT
            )
            """))

            datos_insertar = df_db.to_dict(orient='records')

            query_insert = text("""
            REPLACE INTO energia_estimada_15min 
            (fecha_hora, fecha, hora, temp_c, humedad_relativa, velocidad_viento, cobertura_nubes, presion_hpa, radiacion_inclinada_kwhm2, energia_estimada_kwh)
            VALUES (:fecha_hora, :fecha, :hora, :temp_c, :humedad_relativa, :velocidad_viento, :cobertura_nubes, :presion_hpa, :radiacion_inclinada_kwhm2, :energia_estimada_kwh)
            """)
            
            connection.execute(query_insert, datos_insertar)

        print(f"✅ Éxito: Se procesaron {len(df_db)} registros a resolución de 15 minutos.")

    except Exception as e:
        print(f"❌ Error al procesar los datos: {e}")

if __name__ == "__main__":
    cargar_energia_estimada_15min()