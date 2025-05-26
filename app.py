import os
import requests
from flask import Flask, request, jsonify
# Ya no necesitamos BeautifulSoup ni urllib.parse ni parse_qs si no extraemos token
# from bs4 import BeautifulSoup
# import urllib.parse as urlparse
# from urllib.parse import parse_qs
from json import JSONDecodeError

app = Flask(__name__)

# Diccionario de mapeo de códigos de estación a nombres para la URL
# IMPORTANTE: ESTO ES UN EJEMPLO. NECESITAS EXPANDIR ESTA LISTA
# CON LAS ESTACIONES RELEVANTES Y SUS SLUGS (NOMBRES PARA LA URL DE ADIF).
STATION_CODE_TO_NAME = {
    "13106": "llodio",
    "71302": "bilbao-abando-indalecio-prieto",
    "71301": "barakaldo",
    "71304": "santurtzi",
    "71305": "muskiz",
    "71306": "gallarta",
    # Añade más estaciones aquí siguiendo el patrón:
    # "CODIGO_NUMERICO": "nombre-de-la-estacion-en-la-url",
}

# Si el token no es dinámico y no se extrae, DEBEMOS ASIGNARLE UN VALOR FIJO
# Si NO SE NECESITA UN TOKEN EN ABSOLUTO, dejarlo como cadena vacía o None
# y quitarlo de la url_post si la API lo permite.
# Para este intento, lo dejaré como una cadena vacía y lo incluiremos en la URL
# Si falla, podrías probar a quitar '&p_p_auth={auth_token}' de url_post
# O si sabes un token fijo que funcione por un tiempo, ponlo aquí:
FIXED_AUTH_TOKEN = "NO_TOKEN_NEEDED_OR_FIXED_VALUE" # O "" si no se usa, o el que descubras


def get_horarios_proxy(cod_estacion_input):
    """
    Obtiene los horarios de ADIF. Este intento omite la petición GET inicial
    y va directamente a la API POST.
    """
    base_adif_url = "https://www.adif.es"
    
    # --- Construcción de la URL base de la estación (para el POST) ---
    station_name_for_url = STATION_CODE_TO_NAME.get(cod_estacion_input, None)

    if station_name_for_url:
        cod_estacion_full_slug = f"{cod_estacion_input}-{station_name_for_url}"
        url_base_with_station = f"{base_adif_url}/w/{cod_estacion_full_slug}"
        app.logger.info(f"Usando URL base de estación para POST: {url_base_with_station}")
    else:
        app.logger.warning(f"No se encontró un nombre de URL para la estación '{cod_estacion_input}' en el mapeo. Intentando con el código tal cual para el POST.")
        url_base_with_station = f"{base_adif_url}/w/{cod_estacion_input}"
        # Si el mapeo es mandatorio y falla aquí, esto sería un error de input
        return {"error": True, "message": f"Código de estación '{cod_estacion_input}' no reconocido o sin nombre asociado para la URL de ADIF."}

    # --- Construir la URL completa para la petición POST ---
    # Asumimos que el token es fijo (o no necesario) y que assetEntryId es fijo
    url_post = (
        url_base_with_station +
        "?p_p_id=servicios_estacion_ServiciosEstacionPortlet"
        "&p_p_lifecycle=2"
        "&p_p_state=normal"
        "&p_p_mode=view"
        "&p_p_resource_id=%2FconsultarHorario"
        "&p_p_cacheability=cacheLevelPage"
        f"&assetEntryId=3127062" # Asumimos que es fijo, basado en tu ejemplo
        f"&p_p_auth={FIXED_AUTH_TOKEN}" # Usamos el token fijo o vacío
    )

    form_data = {
        "_servicios_estacion_ServiciosEstacionPortlet_searchType": "proximasSalidas",
        "_servicios_estacion_ServiciosEstacionPortlet_trafficType": "cercanias",
        "_servicios_estacion_ServiciosEstacionPortlet_numPage": "0",
        "_servicios_estacion_ServiciosEstacionPortlet_commuterNetwork": "BILBAO", # Ajusta si necesitas que sea dinámico
        "_servicios_estacion_ServiciosEstacionPortlet_stationCode": cod_estacion_input # Usar el código numérico original
    }

    headers_post = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36", # User-Agent actualizado
        "Referer": url_base_with_station, # El Referer debe ser la URL de la página de la estación, incluso si no la "visitamos" directamente
        "Origin": base_adif_url,
        "X-Requested-With": "XMLHttpRequest",
        # Añade aquí otros headers comunes si la petición POST también es bloqueada:
        "Accept": "application/json, text/javascript, */*; q=0.01", # Más apropiado para una API JSON
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
        # Estos Sec-Fetch son más para el GET inicial, pero no hacen daño aquí
        "Sec-Fetch-Dest": "empty", # Típicamente 'empty' para llamadas AJAX
        "Sec-Fetch-Mode": "cors",  # O 'no-cors' dependiendo de la configuración del server
        "Sec-Fetch-Site": "same-origin", # Si el origen es el mismo que la URL POST
    }
    
    with requests.Session() as session:
        app.logger.info(f"Realizando petición POST directa a ADIF. URL: {url_post}")
        try:
            response = session.post(url_post, data=form_data, headers=headers_post, timeout=20)
            response.raise_for_status() # Lanza excepción para códigos de estado HTTP 4xx/5xx
            
            content_type = response.headers.get("Content-Type", "")
            if "application/json" in content_type:
                app.logger.info("Respuesta JSON obtenida de ADIF.")
                return response.json()
            else:
                app.logger.warning(f"Respuesta de ADIF no es JSON. Content-Type: {content_type}. Respuesta (parcial): {response.text[:200]}")
                return {"error": True, "message": "La respuesta de ADIF no fue JSON.", "details": response.text[:500]}

        except requests.exceptions.HTTPError as http_err:
            app.logger.error(f"Error HTTP de ADIF (POST directo): {http_err}. Respuesta (parcial): {response.text[:500] if response else 'No response text'}")
            return {"error": True, "message": f"Error HTTP de ADIF ({http_err.response.status_code if http_err.response else 'Unknown'}).", "details": response.text[:500] if response else 'No response text'}
        except JSONDecodeError:
            app.logger.error(f"Error al decodificar JSON de ADIF (POST directo). Respuesta (parcial): {response.text[:500]}")
            return {"error": True, "message": "Respuesta de ADIF JSON inválida.", "details": response.text[:500]}
        except requests.exceptions.RequestException as req_err:
            app.logger.error(f"Error en la petición a ADIF (POST directo): {req_err}")
            return {"error": True, "message": "Error en la petición a ADIF.", "details": str(req_err)}

# Ruta para consultar horarios via API proxy
@app.route("/api/horarios/<cod_estacion>")
def api_horarios(cod_estacion):
    app.logger.info(f"Recibida petición API para estación: {cod_estacion}")
    if not cod_estacion or not cod_estacion.isalnum():
        app.logger.warning(f"Código de estación inválido recibido: {cod_estacion}")
        return jsonify({"error": True, "message": "Código de estación inválido."}), 400
        
    result = get_horarios_proxy(cod_estacion)
    if result.get("error"):
        status_code = 500
        # Adaptar los mensajes de error ya que ahora solo hay una petición
        if "Error HTTP de ADIF" in result.get("message", ""):
            status_code = 502 # Bad Gateway
        elif "no reconocido o sin nombre asociado" in result.get("message", ""):
            status_code = 400 # Bad Request si el código no está mapeado
        return jsonify(result), status_code
    return jsonify(result)

if __name__ == "__main__":
    app.logger.setLevel(os.environ.get("LOGLEVEL", "INFO").upper())
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
