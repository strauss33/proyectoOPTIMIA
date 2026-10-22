from datosDiarios import growatt_diaria
from datosDiarios import climaHistoricoNASA_diario
from datosDiarios import pronostico_diario_openMeteo
from datosDiarios import climaHistoricoOpenMeteo_diario
from EstimarEnergia import growatt_diaria_15min
from EstimarEnergia import pronostico_15min_5days
from EstimarEnergia import energia_pronosticada_15min


print("[1/7] Actualizando Generación Growatt...")
growatt_diaria.ejecutar_mantenimiento()

print("[2/7] Actualizando Histórico NASA...")
climaHistoricoNASA_diario.actualizar_clima_diario()

print("[3/7] Actualizando Histórico Open-Meteo...")
climaHistoricoOpenMeteo_diario.actualizar_clima_openmeteo_diario()

print("[4/7] Obteniendo Pronóstico a 7 días...")
pronostico_diario_openMeteo.obtener_pronostico()

print("[5/7] Obteniendo generacion Growatt de cada 15min...")
growatt_diaria_15min.ejecutar_carga_dia_anterior()

print("[6/7] Obteniendo el pronóstico de cada 15 minutos a 5 días...")
pronostico_15min_5days.obtener_pronostico_15min()

print("[7/7] Obteniendo la estimacion de energía de cada 15 minutos a 5 días...")
energia_pronosticada_15min.estimar_energia_pronosticada()

print("--- PROCESO FINALIZADO CON ÉXITO ---")