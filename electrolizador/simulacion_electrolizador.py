import pandas as pd
import numpy as np
from sqlalchemy import create_engine

# ==========================================
# 1. CONFIGURACIÓN DE CONEXIÓN A MYSQL
# ==========================================
DB_USER = "root"
DB_PASSWORD = ""
DB_HOST = "localhost"
DB_PORT = "3306"
DB_NAME = "datos"

connection_string = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(connection_string)

# ==========================================
# 2. PARÁMETROS FÍSICOS Y OPERATIVOS (ELECTROLIZADOR Y FUEL CELL)
# ==========================================
# --- Electrolizador (Modelo JM-500) ---
P_MAX = 260.0          # W (Consumo eléctrico máximo del JM-500)
P_MIN = 30.0           # W (Umbral mínimo de encendido operativo)
FLUJO_MAX_H2 = 510.0   # mL/min a máxima potencia (según hoja de datos)
VOLUMEN_MOLAR = 24450.0 # mL/mol (a 25 °C y 1 atm)

# Constante de los gases ideales y temperatura ambiente de referencia
R = 0.08314            # (L * bar) / (mol * K)
T = 298.15             # K (25 °C)

# --- Tanques de Almacenamiento (Especificaciones del Profesor) ---
# Tanto el tanque de H2 como los tubos de O2 son de 100 Litros.
# Se llenan hasta una presión nominal de 3.0 bar (aprox. 10 horas a flujo nominal de 510 mL/min).
VOLUMEN_TANQUE_H2 = 100.0  # Litros (Tanque pulmón de H2 para abastecer la casa)
VOLUMEN_TANQUE_O2 = 100.0  # Litros (Capacidad por tubo de O2)

P_TANK_MIN = 0.0           # bar (Presión mínima de trabajo - vacío relativo/útil)
P_TANK_MAX = 3.0           # bar (Presión de llenado completo / sustitución de tubo)

# Moles máximos permitidos en un tanque de 100 L a 3.0 bar según Ley de Gases Ideales:
# n = (P * V) / (R * T) => (3.0 * 100.0) / (0.08314 * 298.15) ≈ 12.10 moles
N_H2_MAX_PERMITIDOS = (P_TANK_MAX * VOLUMEN_TANQUE_H2) / (R * T)
N_O2_MAX_PERMITIDOS = (P_TANK_MAX * VOLUMEN_TANQUE_O2) / (R * T)

# --- Pila de Combustible (Fuel Cell - PEM) ---
# Utiliza el H2 acumulado en el tanque y toma O2 directamente del aire ambiente
# para abastecer la demanda eléctrica del hogar cuando no hay generación solar suficiente.
ETA_FUEL_CELL = 0.50          # Eficiencia eléctrica típica de celda PEM (~50%)
LHV_H2_J_MOL = 241820.0       # J/mol (Poder Calorífico Inferior - LHV del H2)
LHV_H2_WH_MOL = LHV_H2_J_MOL / 3600.0  # ~67.17 Wh/mol
ENERGIA_ELEC_WH_POR_MOL = ETA_FUEL_CELL * LHV_H2_WH_MOL  # ~33.59 Wh eléctricos por cada mol de H2
P_FC_MAX = 500.0              # W (Potencia máxima eléctrica que puede entregar la Fuel Cell; ajustable según modelo)

# Paso temporal de integración (15 minutos = 0.25 horas)
DELTA_T = 0.25

# ==========================================
# 3. CARGA Y CRUCE DE DATOS (PV Y CONSUMO)
# ==========================================
query_pv = "SELECT fecha_hora, potencia_w FROM growatt_produccion_intradia ORDER BY fecha_hora ASC"
query_load = "SELECT fecha_hora, consumo_w FROM growatt_consumo_intradia ORDER BY fecha_hora ASC"

print("Cargando datos fotovoltaicos y de consumo desde la base de datos...")
df_pv = pd.read_sql(query_pv, con=engine)
df_load = pd.read_sql(query_load, con=engine)

df_pv['fecha_hora'] = pd.to_datetime(df_pv['fecha_hora'])
df_load['fecha_hora'] = pd.to_datetime(df_load['fecha_hora'])

# Homogeneizar resolución: Pasar el consumo de 5 min a 15 min
df_load_15m = df_load.set_index('fecha_hora').resample('15min').mean().reset_index()

# Unir ambas tablas por timestamp
df_merged = pd.merge(df_pv, df_load_15m, on='fecha_hora', how='inner')

# Potencia neta: Excedente solar o Déficit de la vivienda
df_merged['potencia_excedente_w'] = (df_merged['potencia_w'] - df_merged['consumo_w']).clip(lower=0.0)
df_merged['potencia_deficit_w'] = (df_merged['consumo_w'] - df_merged['potencia_w']).clip(lower=0.0)

# ==========================================
# 4. SIMULACIÓN DINÁMICA DE ACOPLAMIENTO H2 / O2 / FUEL CELL
# ==========================================
def simular_historico_h2_o2(df, v_h2_litros, v_o2_litros):
    print("Iniciando simulación temporal...")
    print(f" - Tanque H2: {v_h2_litros} L (Máx {P_TANK_MAX} bar = {N_H2_MAX_PERMITIDOS:.2f} mol)")
    print(f" - Tanque O2: {v_o2_litros} L por tubo (Máx {P_TANK_MAX} bar = {N_O2_MAX_PERMITIDOS:.2f} mol con recambio)")
    print(f" - Pila de Combustible (Fuel Cell): η = {ETA_FUEL_CELL*100:.0f}%, P_máx = {P_FC_MAX} W (O2 del aire)")

    # Estado inicial del almacenamiento (arranque con tanques vacíos a 0 bar)
    n_h2_inv = 0.0  # Moles acumulados en el tanque de H2
    n_o2_inv = 0.0  # Moles acumulados en el tubo de O2 actualmente en carga

    # Contador de tubos de oxígeno de 100 L llenos (3.0 bar) retirados
    tubos_o2_cargados = 0

    # Acumuladores para balance global
    n_h2_total_gen = 0.0
    n_h2_total_cons = 0.0
    n_o2_total_gen = 0.0

    resultados = []

    for idx, row in df.iterrows():
        p_pv = row['potencia_w']
        p_consumo = row['consumo_w']
        p_excedente = row['potencia_excedente_w']
        p_deficit = row['potencia_deficit_w']

        # -------------------------------------------------------------
        # A. GENERACIÓN DE HIDRÓGENO Y OXÍGENO (ELECTROLIZADOR JM-500)
        # Opera únicamente si existe excedente solar suficiente (>= P_MIN)
        # -------------------------------------------------------------
        if p_excedente >= P_MAX:
            p_electrolizador = P_MAX
        elif P_MIN <= p_excedente < P_MAX:
            p_electrolizador = p_excedente
        else:
            p_electrolizador = 0.0

        if p_electrolizador > 0.0:
            ratio = (p_electrolizador - P_MIN) / (P_MAX - P_MIN)
            flujo_h2_gen = ratio * FLUJO_MAX_H2  # mL/min
        else:
            flujo_h2_gen = 0.0

        # Moles generados en el intervalo (15 min = DELTA_T horas)
        n_h2_gen_paso = (flujo_h2_gen * 60.0 / VOLUMEN_MOLAR) * DELTA_T
        n_o2_gen_paso = 0.5 * n_h2_gen_paso  # Estequiometría: 2 H2O -> 2 H2 + O2

        n_h2_total_gen += n_h2_gen_paso
        n_o2_total_gen += n_o2_gen_paso

        # -------------------------------------------------------------
        # B. CONSUMO DE HIDRÓGENO POR LA FUEL CELL (DÉFICIT EN LA CASA)
        # La pila utiliza H2 del tanque y O2 del aire exterior para suplir la demanda
        # -------------------------------------------------------------
        if p_deficit > 0.0 and n_h2_inv > 0.0:
            # Potencia demandada a la pila (limitada por P_FC_MAX)
            p_fc_objetivo = min(p_deficit, P_FC_MAX)
            energia_fc_wh = p_fc_objetivo * DELTA_T  # Wh requeridos en estos 15 min
            n_h2_necesario = energia_fc_wh / ENERGIA_ELEC_WH_POR_MOL

            if n_h2_inv >= n_h2_necesario:
                # El tanque tiene suficiente H2 para cubrir la demanda
                n_h2_cons_paso = n_h2_necesario
                p_fuel_cell = p_fc_objetivo
            else:
                # El tanque se agota parcialmente cubriendo lo que alcanza
                n_h2_cons_paso = n_h2_inv
                p_fuel_cell = (n_h2_cons_paso * ENERGIA_ELEC_WH_POR_MOL) / DELTA_T

            flujo_h2_cons = (n_h2_cons_paso / DELTA_T) * VOLUMEN_MOLAR / 60.0  # mL/min
        else:
            n_h2_cons_paso = 0.0
            p_fuel_cell = 0.0
            flujo_h2_cons = 0.0

        n_h2_total_cons += n_h2_cons_paso
        p_deficit_restante = max(0.0, p_deficit - p_fuel_cell)

        # -------------------------------------------------------------
        # C. BALANCE DINÁMICO EN EL TANQUE DE HIDRÓGENO (H2)
        # Se suma lo producido por el sol y se resta lo consumido por la casa
        # -------------------------------------------------------------
        n_h2_inv = n_h2_inv + n_h2_gen_paso - n_h2_cons_paso
        n_h2_inv = max(0.0, n_h2_inv)

        # Límite físico de seguridad: Válvula de alivio a 3.0 bar
        if n_h2_inv > N_H2_MAX_PERMITIDOS:
            n_h2_inv = N_H2_MAX_PERMITIDOS

        # Presión instantánea en el tanque de H2
        presion_h2 = (n_h2_inv * R * T) / v_h2_litros

        # -------------------------------------------------------------
        # D. ACUMULACIÓN Y SUSTITUCIÓN DE TUBOS DE OXÍGENO (O2)
        # Se llena el tubo actual de 100 L. Al llegar a 3.0 bar se sustituye por uno vacío.
        # -------------------------------------------------------------
        n_o2_inv = n_o2_inv + n_o2_gen_paso

        while n_o2_inv >= N_O2_MAX_PERMITIDOS:
            tubos_o2_cargados += 1
            n_o2_inv -= N_O2_MAX_PERMITIDOS  # El excedente comienza a llenar el nuevo tubo

        n_o2_inv = max(0.0, n_o2_inv)
        presion_o2 = (n_o2_inv * R * T) / v_o2_litros

        # Registro del paso temporal
        resultados.append({
            'timestamp': row['fecha_hora'],
            'p_pv_w': p_pv,
            'consumo_casa_w': p_consumo,
            'p_excedente_w': p_excedente,
            'p_deficit_w': p_deficit,
            'p_electrolizador_w': p_electrolizador,
            'p_fuel_cell_w': p_fuel_cell,
            'p_deficit_restante_w': p_deficit_restante,
            'flujo_h2_ml_min': flujo_h2_gen,
            'flujo_h2_gen_ml_min': flujo_h2_gen,
            'flujo_h2_cons_ml_min': flujo_h2_cons,
            'n_h2_gen_mol_h': n_h2_gen_paso / DELTA_T,
            'n_h2_cons_mol_h': n_h2_cons_paso / DELTA_T,
            'n_h2_mol': n_h2_inv,
            'presion_h2_bar': presion_h2,
            'n_o2_gen_mol_h': n_o2_gen_paso / DELTA_T,
            'n_o2_mol': n_o2_inv,
            'presion_o2_bar': presion_o2,
            'tubos_o2_cargados': tubos_o2_cargados,
            'n_o2_total_gen_mol': n_o2_total_gen
        })

    df_res = pd.DataFrame(resultados)
    
    # Resumen de resultados clave por consola
    print("\n--- RESUMEN DE LA SIMULACIÓN ---")
    print(f"Total registros procesados: {len(df_res)}")
    print(f"Hidrógeno total generado: {n_h2_total_gen:.2f} mol ({(n_h2_total_gen * VOLUMEN_MOLAR / 1000):.1f} L a 1 atm)")
    print(f"Hidrógeno total consumido por Fuel Cell: {n_h2_total_cons:.2f} mol ({(n_h2_total_cons * VOLUMEN_MOLAR / 1000):.1f} L a 1 atm)")
    print(f"Hidrógeno remanente en tanque: {n_h2_inv:.2f} mol ({presion_h2:.2f} bar)")
    print(f"Oxígeno total generado: {n_o2_total_gen:.2f} mol ({(n_o2_total_gen * VOLUMEN_MOLAR / 1000):.1f} L a 1 atm)")
    print(f"Tubos de O2 de 100 L cargados a {P_TANK_MAX} bar y sustituidos: {tubos_o2_cargados}")
    print(f"Presión del tubo actual de O2 en proceso de llenado: {presion_o2:.2f} bar ({n_o2_inv:.2f} mol)")
    
    return df_res

# ==========================================
# 5. EJECUCIÓN Y GUARDADO EN LA BASE DE DATOS
# ==========================================
df_simulacion = simular_historico_h2_o2(df_merged, VOLUMEN_TANQUE_H2, VOLUMEN_TANQUE_O2)

if not df_simulacion.empty:
    print(f"\nGuardando serie temporal en la base de datos (tabla 'simulacion_h2_15min')...")
    df_simulacion.to_sql('simulacion_h2_15min', con=engine, if_exists='replace', index=False)
    print("¡Proceso finalizado y guardado correctamente!")
else:
    print("No se generaron resultados en la simulación.")
