import os
import requests
from flask import Flask, jsonify, request # 'request' no se usa directamente en este código, pero es común
from json import JSONDecodeError
import logging
import re # Para la extracción de token, aunque no se usa en esta versión de 'token fijo'

app = Flask(__name__)

# Configurar el logging para Flask para ver las trazas en Render
logging.basicConfig(level=logging.INFO)
app.logger.setLevel(logging.INFO)

# --- ADVERTENCIAS CRÍTICAS ---
# 1. TOKEN FIJO: Este código ASUME que el token 'p_p_auth' es fijo.
#    Es EXTREMADAMENTE improbable que esto funcione con ADIF en producción,
#    ya que los tokens son dinámicos por seguridad. Espera errores 400/403.
# 2. BLOQUEO DE IP: Las IPs de Render son de centro de datos.
#    ADIF muy probablemente bloqueará las peticiones con un 403 Forbidden.
#    Si esto sucede, la única solución fiable es un proxy residencial o una API de scraping.
# -----------------------------

# --- TOKEN FIJO (REEMPLAZA CON EL QUE HAYAS OBSERVADO O ASUMIDO) ---
# Si has observado un token que parece repetirse por un tiempo, puedes ponerlo aquí.
# De lo contrario, este es solo un valor de ejemplo.
# Los tokens reales son dinámicos y deberían ser extraídos.
FIXED_AUTH_TOKEN = "6O7tIjAO" # ¡Reemplaza con tu token si tienes uno!
# --- FIN TOKEN FIJO ---

# Diccionario de mapeo de códigos de estación a nombres para la URL de ADIF
STATION_CODE_TO_NAME = {
    "13106": "llodio",
    "71302": "bilbao-abando-indalecio-prieto",
    "71301": "barakaldo",
    "71304": "santurtzi",
    "71305": "muskiz",
    "71306": "gallarta",
    # Añade más estaciones aquí según sea necesario
    # Asegúrate de que los nombres coincidan exactamente con los slugs de ADIF
}

# Definir el USER_AGENT
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"


@app.route("/api/horarios/<cod_estacion>", methods=["GET"])
def get_horarios_api(cod_estacion):
    """
    API para obtener horarios de ADIF para una estación dinámica.
    Asume que el token p_p_auth es fijo.
    """
    app.logger.info(f"Recibida petición API para estación: {cod_estacion}")

    if not cod_estacion or not cod_estacion.isalnum():
        app.logger.warning(f"Código de estación inválido recibido: {cod_estacion}")
        return jsonify({"error": True, "message": "Código de estación inválido."}), 400

    station_name_for_url = STATION_CODE_TO_NAME.get(cod_estacion, None)

    if not station_name_for_url:
        app.logger.warning(f"Código de estación '{cod_estacion}' no reconocido o sin nombre asociado para la URL de ADIF.")
        return jsonify({"error": True, "message": f"Código de estación '{cod_estacion}' no reconocido o sin nombre asociado para la URL de ADIF."}), 400

    base_adif_url = "https://www.adif.es"
    
    # Construir la URL base de la estación
    url_base_with_station = f"{base_adif_url}/w/{cod_estacion}-{station_name_for_url}".strip()

    # Construir la URL completa para la petición POST
    url_post = (
        url_base_with_station +
        "?p_p_id=servicios_estacion_ServiciosEstacionPortlet"
        "&p_p_lifecycle=2"
        "&p_p_state=normal"
        "&p_p_mode=view"
        "&p_p_resource_id=%2FconsultarHorario"
        "&p_p_cacheability=cacheLevelPage"
        f"&assetEntryId=3127062" 
        f"&p_p_auth={FIXED_AUTH_TOKEN.strip()}" # Usando el token fijo, con .strip()
    )

    form_data = {
        "_servicios_estacion_ServiciosEstacionPortlet_searchType": "proximasSalidas",
        "_servicios_estacion_ServiciosEstacionPortlet_trafficType": "cercanias",
        "_servicios_estacion_ServiciosEstacionPortlet_numPage": "0",
        "_servicios_estacion_ServiciosEstacionPortlet_commuterNetwork": "BILBAO", # Asumimos que la red es BILBAO
        "_servicios_estacion_ServiciosEstacionPortlet_stationCode": cod_estacion # Usando el código de estación dinámico
    }

    headers_post = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": USER_AGENT,
        "Referer": url_base_with_station,
        "Origin": base_adif_url,
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }
    
    with requests.Session() as session:
        app.logger.info(f"Realizando petición POST a ADIF. URL: {url_post}")
        try:
            response = session.post(url_post, data=form_data, headers=headers_post, timeout=20)
            response.raise_for_status() # Lanza un HTTPError para 4xx/5xx
            
            content_type = response.headers.get("Content-Type", "")
            if "application/json" in content_type:
                app.logger.info("Respuesta JSON obtenida de ADIF.")
                return jsonify(response.json())
            else:
                app.logger.warning(f"Respuesta de ADIF no es JSON. Content-Type: {content_type}. Respuesta (parcial): {response.text[:200]}")
                return jsonify({"error": True, "message": "La respuesta de ADIF no fue JSON.", "details": response.text[:500]}), 502

        except requests.exceptions.HTTPError as http_err:
            app.logger.error(f"Error HTTP de ADIF (POST): {http_err}. Status: {http_err.response.status_code if http_err.response else 'N/A'}. Respuesta (parcial): {http_err.response.text[:500] if http_err.response else 'No response text'}")
            return jsonify({"error": True, "message": f"Error HTTP de ADIF: {http_err.response.status_code if http_err.response else 'Unknown'}.", "details": http_err.response.text[:500] if http_err.response else str(http_err)}), http_err.response.status_code if http_err.response else 500
        except JSONDecodeError:
            app.logger.error(f"Error al decodificar JSON de ADIF (POST). Respuesta (parcial): {response.text[:500]}")
            return jsonify({"error": True, "message": "Respuesta de ADIF JSON inválida.", "details": response.text[:500]}), 502
        except requests.exceptions.RequestException as req_err:
            app.logger.error(f"Error en la petición a ADIF (POST): {req_err}")
            return jsonify({"error": True, "message": "Error en la petición a ADIF.", "details": str(req_err)}), 500

if __name__ == "__main__":
    app.logger.setLevel(os.environ.get("LOGLEVEL", "INFO").upper())
    port = int(os.environ.get("PORT", 5000))
    # Gunicorn es el encargado de ejecutar la app en Render, no este app.run()
    # Esto es solo para pruebas locales.
    app.run(host="0.0.0.0", port=port, debug=True)
