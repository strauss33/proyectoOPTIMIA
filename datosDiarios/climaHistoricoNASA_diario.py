# Carga las herramientas para conectarse a internet (API de la NASA), a la base de datos y manejar fechas.
import requests
import mysql.connector
from datetime import datetime, timedelta

# --- CONFIGURACIÓN ---
# Son las coordenadas geográficas exactas de Villa Mercedes. La NASA las usa para devolver el clima de esa posición específica.
LAT = "-33.64451720576176"
LON = "-65.44526071823961"


#La misma configuración para conectarse a MySQL en XAMPP.
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "datos" 
}

def actualizar_clima_diario():
    # 1. Definimos la ventana de revisión: desde hace 30 días hasta hoy
    # Esto asegura que si la radiación tardó 4 o 5 días, la atrapemos apenas aparezca
    fecha_inicio = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
    fecha_fin = datetime.now().strftime("%Y%m%d")
    
    #Construye la dirección de la API pidiendo tres cosas específicas: T2M: Temperatura a 2 metros de altura. RH2M: Humedad relativa. ALLSKY_SFC_SW_DWN: Radiación solar (irradiancia) que llega al suelo.
    url = f"https://power.larc.nasa.gov/api/temporal/daily/point?parameters=T2M,RH2M,ALLSKY_SFC_SW_DWN&community=RE&longitude={LON}&latitude={LAT}&start={fecha_inicio}&end={fecha_fin}&format=JSON"
    
    print(f"[*] Revisando ventana de clima: {fecha_inicio} al {fecha_fin}...")
    
    # --- Procesamiento de los Datos de la NASA --- 
    try:
        # Hace la "llamada" a la NASA para pedir los datos.
        response = requests.get(url, timeout=30)
        if response.status_code != 200: return
        
        # Convierte la respuesta en un diccionario de Python.
        data = response.json()
        params = data['properties']['parameter']
        t_dict = params['T2M']
        h_dict = params['RH2M']
        r_dict = params['ALLSKY_SFC_SW_DWN']
        # t_dict, h_dict, r_dict Extrae por separado las listas de temperaturas, humedad y radiación que envió el satélite.
        
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # --- Guardado ---
        actualizados = 0

        # Empieza a recorrer día por día los datos recibidos.
        for fecha_str, temp in t_dict.items():
            hum = h_dict[fecha_str]
            rad = r_dict[fecha_str]
            
            # CRÍTICO: Solo guardamos si TODOS los datos están listos (no son -999)
            # Esto evita que guardemos una fila con temperatura pero sin radiación
            # Este if asegura que solo se guarde el dia en la base de datos cuando los tres valores estén completos.
            if temp > -900 and hum > -900 and rad > -900:
                fecha_db = datetime.strptime(fecha_str, "%Y%m%d").strftime("%Y-%m-%d")
                
                query = "REPLACE INTO clima_historico_nasa (fecha, temperatura_media, humedad_relativa, radiacion_solar) VALUES (%s, %s, %s, %s)"
                cursor.execute(query, (fecha_db, temp, hum, rad))
                actualizados += 1
        #fecha_db = ...: Convierte el formato de fecha de la NASA (20260415) al formato que entiende MySQL (2026-04-15).
        # REPLACE INTO clima_historico...: Al igual que en el script de Growatt, esto sobreescribe los datos. Si hace dos días guardaste la temperatura pero la radiación era -999, hoy que la radiación ya está disponible, el script actualizará la fila completa con los valores reales.

        conn.commit()
        # Guarda los cambios


        cursor.close()
        conn.close()
        print(f"[V] Clima: Se revisaron los últimos 30 días. {actualizados} días quedaron completos en la BD.")

    except Exception as e:
        print(f"[X] Error en actualización de clima: {e}")

if __name__ == "__main__":
    actualizar_clima_diario()