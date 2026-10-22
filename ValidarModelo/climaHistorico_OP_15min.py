import mysql.connector
import requests

LAT = "-33.644517"
LON = "-65.445261"

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "datos",
}


def get_open_meteo_15min_rango(start_date, end_date):
    # Variables con sus nombres exactos en la API de Open-Meteo
    variables = [
        "temperature_2m",
        "relative_humidity_2m",
        "shortwave_radiation",
        "wind_speed_10m",
        "cloud_cover",
        "surface_pressure",
        "direct_normal_irradiance",
        "diffuse_radiation",
    ]

    # Probar primero en Archive API y si falla probar en Forecast API
    urls = [
        "https://archive-api.open-meteo.com/v1/archive",
        "https://api.open-meteo.com/v1/forecast",
    ]

    for url_base in urls:
        url = (
            f"{url_base}?"
            f"latitude={LAT}&longitude={LON}&start_date={start_date}&end_date={end_date}"
            f"&minutely_15={','.join(variables)}"
            f"&timezone=America%2FArgentina%2FSan_Luis"
        )

        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                data = response.json().get("minutely_15")
                if data and "time" in data:
                    print(f"[*] Datos obtenidos correctamente desde: {url_base}")
                    return data
            else:
                print(f"[!] {url_base} devolvió HTTP {response.status_code}")
        except Exception as e:
            print(f"[!] Error al conectar con {url_base}: {e}")

    return None


def crear_tabla_si_no_existe(cursor):
    query = """
    CREATE TABLE IF NOT EXISTS clima_15min_openmeteo (
        fecha_hora DATETIME PRIMARY KEY,
        temperatura FLOAT,
        humedad_relativa FLOAT,
        radiacion_solar FLOAT,
        velocidad_viento FLOAT,
        cobertura_nubes FLOAT,
        presion_superficie FLOAT,
        radiacion_directa FLOAT,
        radiacion_difusa FLOAT
    )
    """
    cursor.execute(query)


def ejecutar_carga_rango():
    start_date = "2026-09-12"
    end_date = "2026-09-16"

    print(f"[*] Solicitando datos climáticos a Open-Meteo del {start_date} al {end_date}...")
    m15_data = get_open_meteo_15min_rango(start_date, end_date)

    if not m15_data:
        print(f"[X] No se pudieron obtener datos para el rango {start_date} a {end_date}.")
        return

    timestamps = m15_data.get("time", [])
    temps = m15_data.get("temperature_2m", [])
    humedades = m15_data.get("relative_humidity_2m", [])
    rad_globals = m15_data.get("shortwave_radiation", [])
    vientos = m15_data.get("wind_speed_10m", [])
    nubes = m15_data.get("cloud_cover", [])
    presiones = m15_data.get("surface_pressure", [])
    rad_directas = m15_data.get("direct_normal_irradiance", [])
    rad_difusas = m15_data.get("diffuse_radiation", [])

    registros = []
    for i in range(len(timestamps)):
        fecha_hora_str = timestamps[i].replace("T", " ")

        t = temps[i]
        h = humedades[i]
        r_glob = rad_globals[i] if (i < len(rad_globals) and rad_globals[i] is not None) else 0.0

        if t is None or h is None:
            continue

        viento = vientos[i] if (i < len(vientos) and vientos[i] is not None) else 2.0
        nube = nubes[i] if (i < len(nubes) and nubes[i] is not None) else 20.0
        presion = presiones[i] if (i < len(presiones) and presiones[i] is not None) else 1013.25
        r_dir = rad_directas[i] if (i < len(rad_directas) and rad_directas[i] is not None) else r_glob * 0.7
        r_dif = rad_difusas[i] if (i < len(rad_difusas) and rad_difusas[i] is not None) else r_glob * 0.3

        registros.append(
            (fecha_hora_str, t, h, r_glob, viento, nube, presion, r_dir, r_dif)
        )

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        crear_tabla_si_no_existe(cursor)

        query = """
        REPLACE INTO clima_15min_openmeteo 
        (fecha_hora, temperatura, humedad_relativa, radiacion_solar, velocidad_viento, cobertura_nubes, presion_superficie, radiacion_directa, radiacion_difusa) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        cursor.executemany(query, registros)
        conn.commit()

        print("-" * 50)
        print(f"[V] ¡RANGO {start_date} AL {end_date} CARGADO CON ÉXITO!")
        print(f"[V] Registros insertados/actualizados: {len(registros)}")
        print("-" * 50)

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"[X] Error durante la conexión/guardado en la base de datos: {e}")


if __name__ == "__main__":
    ejecutar_carga_rango()