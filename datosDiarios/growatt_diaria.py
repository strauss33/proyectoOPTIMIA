# Cargamos las librerías para hacer peticiones web, conectarse a MySQL, 
# manejar formato JSON y trabajar con fechas. 

import requests 
import mysql.connector
import json
from datetime import datetime, timedelta  

# --- Credenciales de acceso y el identificador único de la planta solar en Growatt. ---
USER = "absch"
PASS = "Unvime24"
PLANT_ID = "2613959"

# --- Base de datos ---
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "datos" 
}

# --- Esta funcion simula la entrada al navegador ---
def get_session():
    session = requests.Session()    
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    })
    login_url = "https://server.growatt.com/login"
    data = {"account": USER, "password": PASS, "validateCode": ""}
    try:
        session.post(login_url, data=data, timeout=10)
        return session
    except Exception as e:
        print(f"Error de sesión: {e}")
        return None
# Con requests.Session() un objeto que "recuerda" que ya te logueaste (guarda las cookies).
# Con session.headers.update Configura un "User-Agent" para que el servidor crea que usas Chrome y no un script de Python. 
# Con session.post envía usuario y contraseña a Growatt para abrir la sesión. 

# --- Acá es donde la información llega a la base de datos. ---
def save_to_db(fecha, valor):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        valor_limpio = round(float(valor), 2)
        # REPLACE asegura que si el dato ya existe (porque antes era 0.0), se actualice al promedio
        query = "REPLACE INTO growatt_produccion (fecha, energia) VALUES (%s, %s)"
        cursor.execute(query, (fecha, valor_limpio))
        conn.commit()
        cursor.close()
        conn.close()
        print(f"[{datetime.now()}] ÉXITO: Guardado {fecha} con {valor_limpio} kWh")
    except Exception as e:
        print(f"Error en base de datos: {e}")

# conn = mysql.connector.connect(**DB_CONFIG): Abre la puerta de MySQL.
# valor_limpio = round(float(valor), 2): Asegura que el número sea decimal y solo tenga dos números después de la coma.
# REPLACE INTO growatt_produccion...:  Si la fecha ya existe en la tabla, borra la vieja y pone la nueva. Esto sirve para actualizar días que antes estaban en 0.0 con el nuevo promedio calculado.
# conn.commit(): Confirma los cambios (sin esto, los datos no se guardan realmente).

# --- Esta parte analiza el mes actual ---
def ejecutar_mantenimiento():
    hoy_dt = datetime.now()
    mes_actual_str = hoy_dt.strftime("%Y-%m")
    dia_actual_idx = hoy_dt.day - 1  # El índice del día de hoy en la lista

    print(f"Iniciando revisión del mes {mes_actual_str}...")

    session = get_session()
    if not session: return

    url = "https://server.growatt.com/energy/compare/getDevicesMonthChart"
    payload = {
        "plantId": PLANT_ID,
        "date": mes_actual_str,
        "jsonData": json.dumps([{"type":"plant","sn":PLANT_ID,"params":"energy,autoEnergy"}])
    }

    try:
        response = session.post(url, data=payload, timeout=15)
        res_json = response.json()
        
        if 'obj' in res_json and len(res_json['obj']) > 0:
            lista_energia = res_json['obj'][0]['datas'].get('energy', [])
            
            # Recorremos desde el día 1 hasta ayer (inclusive)
            # Usamos range(dia_actual_idx) para no procesar el día de "hoy" que está incompleto
            for i in range(dia_actual_idx):
                # Construimos la fecha del día que estamos revisando
                fecha_revisada = hoy_dt.replace(day=i+1).strftime("%Y-%m-%d")
                valor_dia = float(lista_energia[i])

                if valor_dia > 0:
                    # Caso normal: tiene datos, guardamos/actualizamos
                    save_to_db(fecha_revisada, valor_dia)
                else:
                    # Caso Especial: El valor es 0.0. Intentamos promediar.
                    # Necesitamos: que no sea el primer día (i>0) y que el día siguiente tenga datos
                    if i > 0 and i + 1 < len(lista_energia):
                        valor_anterior = float(lista_energia[i-1])
                        valor_siguiente = float(lista_energia[i+1])

                        if valor_anterior > 0 and valor_siguiente > 0:
                            promedio = (valor_anterior + valor_siguiente) / 2
                            print(f"[*] Hueco en {fecha_revisada} detectado. Aplicando promedio: {promedio} kWh")
                            save_to_db(fecha_revisada, promedio)
                        else:
                            # Guardamos el 0.0 por ahora, se corregirá mañana cuando haya valor siguiente
                            save_to_db(fecha_revisada, 0.0)
                            print(f"[!] {fecha_revisada} está en 0.0 y no hay datos suficientes para promediar aún.")
                    else:
                        # Si es el día 1 del mes y da 0, no tenemos "anterior" para promediar
                        save_to_db(fecha_revisada, 0.0)

        else:
            print("No se recibió respuesta válida de Growatt.")

    except Exception as e:
        print(f"Error durante la extracción: {e}")

# hoy_dt = datetime.now(): Obtiene la fecha y hora de este momento. 
# url = ".../getDevicesMonthChart": La dirección específica de Growatt donde están los datos del gráfico mensual.
# payload = { ... }: El "formulario" invisible que le enviamos a la web diciendo qué planta y qué mes queremos ver.
# res_json = response.json(): Convierte la respuesta del servidor (que viene como texto) en un formato que Python entiende.
# for i in range(dia_actual_idx):: Un bucle que recorre cada día del mes, desde el día 1 hasta ayer. (No procesa "hoy" porque el día no ha terminado).
# if valor_dia > 0:: Si el día tiene energía, lo manda directo a la base de datos.
# else: (Caso Especial): Si el valor es 0.0 (el inversor se desconectó, por ejemplo):
# valor_anterior y valor_siguiente: Mira cuánto produjo el día antes y el día después.
# promedio = (ant + sig) / 2: Si ambos existen, inventa un dato justo en medio para que la estadística no tenga un pozo vacío.
# print(...): Te avisa en la consola que detectó un hueco y lo reparó.

if __name__ == "__main__":
    ejecutar_mantenimiento()

# Esto simplemente dice: "Si ejecutas este archivo directamente, empieza a correr la función de mantenimiento".