import os
import requests
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup # Necesario para parsear HTML si aún se usa para algo más
import urllib.parse as urlparse # Necesario si parse_qs se usa para algo
from urllib.parse import parse_qs # Necesario si se usa para algo
import re # ¡Necesario para la expresión regular de obtención de token!
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

# Definir el USER_AGENT que ha funcionado previamente
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"


# --- Función para obtener el token (basada en tu código que ha funcionado) ---
def obtener_token(session, url):
    """
    Intenta obtener el token p_p_auth de la URL dada.
    Utiliza los headers que han funcionado previamente y una expresión regular.
    """
    headers_get_token = { # Renombrado para evitar conflicto con headers_get más abajo
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "TE": "trailers"
    }

    try:
        app.logger.info(f"Intentando obtener token de: {url}")
        response = session.get(url, headers=headers_get_token, timeout=20) # Añadido timeout
        response.raise_for_status() # Lanza excepción para códigos de estado HTTP 4xx/5xx
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error al hacer la petición GET para obtener token: {e}")
        return None

    match = re.search(r'p_p_auth=([a-zA-Z0-9\-_]+)', response.text) # Ajustado regex para incluir - y _
    if match:
        token = match.group(1)
        app.logger.info(f"Token p_p_auth encontrado: {token}")
        return token
    else:
        app.logger.warning("No se encontró el token p_p_auth en la página.")
        return None

# --- Fin de la función obtener_token ---


def get_horarios_proxy(cod_estacion_input):
    """
    Obtiene los horarios de ADIF. Primero realiza un GET para obtener el token,
    luego un POST a la API con el token y los datos del formulario.
    """
    base_adif_url = "https://www.adif.es"
    
    # --- Construcción de la URL base de la estación (para el GET inicial y Referer) ---
    station_name_for_url = STATION_CODE_TO_NAME.get(cod_estacion_input, None)

    if station_name_for_url:
        cod_estacion_full_slug = f"{cod_estacion_input}-{station_name_for_url}"
        url_base_with_station = f"{base_adif_url}/w/{cod_estacion_full_slug}"
        app.logger.info(f"Usando URL base de estación: {url_base_with_station}")
    else:
        app.logger.warning(f"No se encontró un nombre de URL para la estación '{cod_estacion_input}' en el mapeo. Intentando con el código tal cual.")
        url_base_with_station = f"{base_adif_url}/w/{cod_estacion_input}"
        # Si el mapeo es mandatorio y falla aquí, esto sería un error de input
        return {"error": True, "message": f"Código de estación '{cod_estacion_input}' no reconocido o sin nombre asociado para la URL de ADIF."}

    with requests.Session() as session:
        # Paso 1: Obtener el token de la página de la estación
        auth_token = obtener_token(session, url_base_with_station)

        if not auth_token:
            app.logger.error("Fallo al obtener el token p_p_auth.")
            return {"error": True, "message": "Fallo al obtener el token de autenticación (p_p_auth) de la página de ADIF."}

        # Paso 2: Construir la URL completa para la petición POST
        # Basado exactamente en tu ejemplo de cómo se construye la URL POST
        url_post = (
            url_base_with_station +
            "?p_p_id=servicios_estacion_ServiciosEstacionPortlet"
            "&p_p_lifecycle=2"
            "&p_p_state=normal"
            "&p_p_mode=view"
            "&p_p_resource_id=%2FconsultarHorario"
            "&p_p_cacheability=cacheLevelPage"
            f"&assetEntryId=3127062" # Asumimos que es fijo, basado en tu ejemplo
            f"&p_p_auth={auth_token}" # ¡Aquí usamos el token dinámico obtenido!
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
            "User-Agent": USER_AGENT, # Usar el mismo User-Agent consistente
            "Referer": url_base_with_station, # El Referer debe ser la URL de la página de la estación
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
        
        app.logger.info(f"Realizando petición POST a ADIF. URL: {url_post}")
        try:
            response = session.post(url_post, data=form_data, headers=headers_post, timeout=20)
            response.raise_for_status()
            
            content_type = response.headers.get("Content-Type", "")
            if "application/json" in content_type:
                app.logger.info("Respuesta JSON obtenida de ADIF.")
                return response.json()
            else:
                app.logger.warning(f"Respuesta de ADIF no es JSON. Content-Type: {content_type}. Respuesta (parcial): {response.text[:200]}")
                return {"error": True, "message": "La respuesta de ADIF no fue JSON.", "details": response.text[:500]}

        except requests.exceptions.HTTPError as http_err:
            app.logger.error(f"Error HTTP de ADIF (POST): {http_err}. Respuesta (parcial): {response.text[:500] if response else 'No response text'}")
            return {"error": True, "message": f"Error HTTP de ADIF ({http_err.response.status_code if http_err.response else 'Unknown'}).", "details": response.text[:500] if response else 'No response text'}
        except JSONDecodeError:
            app.logger.error(f"Error al decodificar JSON de ADIF (POST). Respuesta (parcial): {response.text[:500]}")
            return {"error": True, "message": "Respuesta de ADIF JSON inválida.", "details": response.text[:500]}
        except requests.exceptions.RequestException as req_err:
            app.logger.error(f"Error en la petición a ADIF (POST): {req_err}")
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
        if "Error HTTP de ADIF" in result.get("message", ""):
            status_code = 502
        elif "Fallo al obtener el token" in result.get("message", ""): # Específico para el error de token
            status_code = 503 # Service Unavailable
        elif "no reconocido o sin nombre asociado" in result.get("message", ""):
            status_code = 400
        return jsonify(result), status_code
    return jsonify(result)

if __name__ == "__main__":
    app.logger.setLevel(os.environ.get("LOGLEVEL", "INFO").upper())
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
