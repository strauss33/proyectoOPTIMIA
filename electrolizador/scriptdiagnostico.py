import pandas as pd
from sqlalchemy import create_engine

# Conexión
DB_USER = "root"
DB_PASSWORD = ""
DB_HOST = "localhost"
DB_PORT = "3306"
DB_NAME = "datos"
engine = create_engine(f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

# Cargar y cruzar igual que en la simulación
df_pv = pd.read_sql("SELECT fecha_hora, potencia_w FROM growatt_produccion_intradia ORDER BY fecha_hora ASC", con=engine)
df_load = pd.read_sql("SELECT fecha_hora, consumo_w FROM growatt_consumo_intradia ORDER BY fecha_hora ASC", con=engine)

df_pv['fecha_hora'] = pd.to_datetime(df_pv['fecha_hora'])
df_load['fecha_hora'] = pd.to_datetime(df_load['fecha_hora'])

df_load_15m = df_load.set_index('fecha_hora').resample('15min').mean().reset_index()
df_merged = pd.merge(df_pv, df_load_15m, on='fecha_hora', how='inner')

df_merged['potencia_excedente_w'] = (df_merged['potencia_w'] - df_merged['consumo_w']).clip(lower=0.0)

# Estadísticas clave
print("--- DIAGNOSTICO DE DATOS ---")
print(f"Total de registros analizados: {len(df_merged)}")
print(f"Promedio de generación PV (W): {df_merged['potencia_w'].mean():.2f}")
print(f"Promedio de consumo de la casa (W): {df_merged['consumo_w'].mean():.2f}")
print(f"Promedio de excedente netos (W): {df_merged['potencia_excedente_w'].mean():.2f}")
print(f"Registros con excedente > 30W (Electrolizador encendido): {(df_merged['potencia_excedente_w'] >= 30.0).sum()}")
print(f"Máximo excedente registrado (W): {df_merged['potencia_excedente_w'].max():.2f}")