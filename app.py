import os
import requests
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
import urllib.parse as urlparse
from urllib.parse import parse_qs
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

# --- Inicio: Lógica de extracción de token ---
def extract_auth_token_from_html(html_content):
    """
    Intenta extraer el token p_p_auth de un input oculto o un enlace en el HTML.
    Este es el punto más frágil y podría necesitar ajustes si ADIF cambia su HTML.
    Se busca el token p_p_auth directamente en el HTML.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    app.logger.debug("Buscando token p_p_auth en el HTML...")

    input_token = soup.find('input', {'type': 'hidden', 'name': 'p_p_auth'})
    if input_token and 'value' in input_token.attrs:
        token = input_token['value']
        app.logger.debug(f"Token p_p_auth encontrado en input oculto: {token}")
        return token
    
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        if 'p_p_auth' in href:
            parsed_url = urlparse.urlparse(href)
            query_params = parse_qs(parsed_url.query)
            if 'p_p_auth' in query_params:
                token = query_params['p_p_auth'][0]
                app.logger.debug(f"Token p_p_auth encontrado en enlace: {token}")
                return token

    app.logger.warning("No se pudo encontrar el token p_p_auth en el HTML de la página.")
    return None

# --- Fin: Lógica de extracción de token ---


def get_horarios_proxy(cod_estacion_input):
    """
    Obtiene los horarios de ADIF, construyendo la URL POST con los parámetros
    y el token extraído de la página inicial de la estación.
    """
    base_adif_url = "https://www.adif.es"
    
    # --- Definición de url_base_with_station ANTES del if/else ---
    url_base_with_station = "" # Inicializar con un valor por defecto o vacío

    # --- Construcción de la URL de la página de la estación (para el GET inicial) ---
    station_name_for_url = STATION_CODE_TO_NAME.get(cod_estacion_input, None)

    if station_name_for_url:
        cod_estacion_full_slug = f"{cod_estacion_input}-{station_name_for_url}"
        url_base_with_station = f"{base_adif_url}/w/{cod_estacion_full_slug}"
        app.logger.info(f"Usando URL base de estación para GET: {url_base_with_station}")
    else:
        app.logger.warning(f"No se encontró un nombre de URL para la estación '{cod_estacion_input}' en el mapeo. Intentando con el código tal cual para el GET.")
        url_base_with_station = f"{base_adif_url}/w/{cod_estacion_input}"
        # Puedes optar por devolver un error aquí si el mapeo es mandatorio
        # return {"error": True, "message": f"Código de estación '{cod_estacion_input}' no reconocido o sin nombre asociado para la URL."}

    # --- Headers para la petición GET (mejorados para evitar 403) ---
    headers_get = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Encoding": "gzip, deflate, br", # Importante: si tu navegador lo envía, requests lo puede manejar
    "Accept-Language": "es-ES,es;q=0.9",
    "Connection": "keep-alive",
    "Host": "www.adif.es", # A veces es útil añadirlo
    "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="125", "Google Chrome";v="125"', # Esto es muy específico de Chrome
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    }
    
    with requests.Session() as session:
        try:
            app.logger.info(f"Realizando GET a: {url_base_with_station} con headers mejorados.")
            main_page_response = session.get(url_base_with_station, headers=headers_get, timeout=20)
            main_page_response.raise_for_status()
            app.logger.info("Página de estación obtenida correctamente para extracción de token.")
        except requests.exceptions.RequestException as e:
            app.logger.error(f"Error al acceder a la página de estación de ADIF (GET): {e}")
            return {"error": True, "message": f"Error al acceder a la página de estación de ADIF (GET).", "details": str(e)}

        # Extraer el token de autenticación del HTML de la página
        auth_token = extract_auth_token_from_html(main_page_response.text)

        if not auth_token:
            app.logger.error("No se pudo extraer el token p_p_auth de la página de ADIF.")
            return {"error": True, "message": "No se pudo extraer el token p_p_auth de la página de ADIF."}

        # --- Construir la URL completa para la petición POST ---
        url_post = (
            url_base_with_station +
            "?p_p_id=servicios_estacion_ServiciosEstacionPortlet"
            "&p_p_lifecycle=2"
            "&p_p_state=normal"
            "&p_p_mode=view"
            "&p_p_resource_id=%2FconsultarHorario"
            "&p_p_cacheability=cacheLevelPage"
            f"&assetEntryId=3127062" # Asumimos que es fijo, basado en tu ejemplo
            f"&p_p_auth={auth_token}"
        )

        form_data = {
            "_servicios_estacion_ServiciosEstacionPortlet_searchType": "proximasSalidas",
            "_servicios_estacion_ServiciosEstacionPortlet_trafficType": "cercanias",
            "_servicios_estacion_ServiciosEstacionPortlet_numPage": "0", # Asegurarse de que es un string
            "_servicios_estacion_ServiciosEstacionPortlet_commuterNetwork": "BILBAO", # Ajusta si necesitas que sea dinámico
            "_servicios_estacion_ServiciosEstacionPortlet_stationCode": cod_estacion_input # Usar el código numérico original
        }

        headers_post = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Referer": url_base_with_station, # El referer debe ser la URL de la página de la estación (GET)
            "Origin": base_adif_url,
            "X-Requested-With": "XMLHttpRequest"
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
        elif "No se pudo extraer" in result.get("message", ""):
            status_code = 503
        return jsonify(result), status_code
    return jsonify(result)

if __name__ == "__main__":
    app.logger.setLevel(os.environ.get("LOGLEVEL", "INFO").upper())
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
