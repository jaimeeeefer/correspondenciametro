import os
import requests
from flask import Flask, request, jsonify # No se necesita render_template_string
from bs4 import BeautifulSoup
import urllib.parse as urlparse
from urllib.parse import parse_qs
# from requests.exceptions import JSONDecodeError # Para Python 3.5+
# Para versiones anteriores de requests o por seguridad, puedes usar:
from json import JSONDecodeError # Asegúrate de que esta importación funcione en tu entorno Python


app = Flask(__name__)

# --- Inicio: Lógica de extracción de token (NECESITA VERIFICACIÓN Y AJUSTE) ---
def extract_auth_token_from_html(html_content, target_resource_id):
    """
    Intenta extraer el token p_p_auth de un contenido HTML.
    Busca un enlace (<a>) que contenga el target_resource_id y extrae
    el p_p_auth de su URL.
    ESTA FUNCIÓN ES UNA HIPÓTESIS Y PROBABLEMENTE NECESITE AJUSTES
    BASADOS EN LA ESTRUCTURA REAL DE LA PÁGINA DE ADIF.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    app.logger.debug(f"Buscando token para resource_id: {target_resource_id}")

    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        if target_resource_id in href:
            app.logger.debug(f"Encontrado <a> tag con resource_id: {href}")
            parsed_url = urlparse.urlparse(href)
            query_params = parse_qs(parsed_url.query)
            if 'p_p_auth' in query_params:
                auth_token = query_params['p_p_auth'][0]
                app.logger.debug(f"Token p_p_auth encontrado: {auth_token}")
                return auth_token
    
    app.logger.warning(f"No se pudo encontrar el token p_p_auth para {target_resource_id} en el HTML.")
    return None
# --- Fin: Lógica de extracción de token ---

def get_horarios_proxy(cod_estacion):
    """
    Obtiene los horarios de ADIF, extrayendo primero un token dinámico.
    """
    base_adif_url = "https://www.adif.es"
    station_page_url = f"{base_adif_url}/w/{cod_estacion}"
    target_resource_id = "/consultarHorario"

    headers_get = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    }
    
    with requests.Session() as session:
        try:
            app.logger.info(f"Accediendo a la página de estación: {station_page_url}")
            main_page_response = session.get(station_page_url, headers=headers_get, timeout=20) # Aumentado timeout
            main_page_response.raise_for_status()
            app.logger.info("Página de estación obtenida correctamente.")
        except requests.exceptions.RequestException as e:
            app.logger.error(f"Error al acceder a la página de estación de ADIF: {e}")
            return {"error": True, "message": f"Error al acceder a la página de estación de ADIF.", "details": str(e)}

        auth_token = extract_auth_token_from_html(main_page_response.text, target_resource_id)

        if not auth_token:
            app.logger.error("No se pudo extraer el token de autenticación de la página de ADIF.")
            return {"error": True, "message": "No se pudo extraer el token de autenticación (p_p_auth) de la página de ADIF."}

        portlet_params = {
            "p_p_id": "servicios_estacion_ServiciosEstacionPortlet",
            "p_p_lifecycle": "2",
            "p_p_state": "normal",
            "p_p_mode": "view",
            "p_p_resource_id": target_resource_id,
            "p_p_cacheability": "cacheLevelPage",
            "assetEntryId": "3127062",
            "p_p_auth": auth_token
        }
        
        api_url = f"{base_adif_url}/w/{cod_estacion}"

        form_data = {
            "_servicios_estacion_ServiciosEstacionPortlet_searchType": "proximasSalidas",
            "_servicios_estacion_ServiciosEstacionPortlet_trafficType": "cercanias",
            "_servicios_estacion_ServiciosEstacionPortlet_numPage": "0", # Como string, a veces los formularios lo envían así
            "_servicios_estacion_ServiciosEstacionPortlet_commuterNetwork": "BILBAO", # Considera si esto debe ser dinámico
            "_servicios_estacion_ServiciosEstacionPortlet_stationCode": cod_estacion
        }

        headers_post = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": station_page_url,
            "Origin": base_adif_url,
            "X-Requested-With": "XMLHttpRequest"
        }
        
        app.logger.info(f"Realizando petición POST a ADIF. Token (parcial): {auth_token[:10]}...")
        try:
            response = session.post(api_url, params=portlet_params, data=form_data, headers=headers_post, timeout=20) # Aumentado timeout
            response.raise_for_status()
            
            content_type = response.headers.get("Content-Type", "")
            if "application/json" in content_type:
                app.logger.info("Respuesta JSON obtenida de ADIF.")
                return response.json()
            else:
                app.logger.warning(f"Respuesta de ADIF no es JSON. Content-Type: {content_type}. Respuesta (parcial): {response.text[:200]}")
                return {"error": True, "message": "La respuesta de ADIF no fue JSON.", "details": response.text[:500]}

        except requests.exceptions.HTTPError as http_err:
            app.logger.error(f"Error HTTP de ADIF: {http_err}. Respuesta (parcial): {response.text[:500] if response else 'No response text'}")
            return {"error": True, "message": f"Error HTTP de ADIF ({http_err.response.status_code if http_err.response else 'Unknown'}).", "details": response.text[:500] if response else 'No response text'}
        except JSONDecodeError:
            app.logger.error(f"Error al decodificar JSON de ADIF. Respuesta (parcial): {response.text[:500]}")
            return {"error": True, "message": "Respuesta de ADIF JSON inválida.", "details": response.text[:500]}
        except requests.exceptions.RequestException as req_err:
            app.logger.error(f"Error en la petición a ADIF: {req_err}")
            return {"error": True, "message": "Error en la petición a ADIF.", "details": str(req_err)}

# Ruta para consultar horarios via API proxy
@app.route("/api/horarios/<cod_estacion>")
def api_horarios(cod_estacion):
    app.logger.info(f"Recibida petición API para estación: {cod_estacion}")
    # Validar o sanear cod_estacion si es necesario
    if not cod_estacion or not cod_estacion.isalnum(): # Ejemplo básico de validación
        app.logger.warning(f"Código de estación inválido recibido: {cod_estacion}")
        return jsonify({"error": True, "message": "Código de estación inválido."}), 400
        
    result = get_horarios_proxy(cod_estacion)
    # Determinar el código de estado HTTP basado en el resultado
    if result.get("error"):
        # Podrías mapear diferentes errores internos a diferentes códigos de estado HTTP
        # Por ahora, un 500 genérico si es error del proxy, o 502 si ADIF falló.
        # Si el error es porque no se pudo extraer el token, podría ser un 503 Service Unavailable.
        # Este es un ejemplo simple:
        status_code = 500 # Error interno del servidor por defecto
        if "Error HTTP de ADIF" in result.get("message", ""):
            status_code = 502 # Bad Gateway
        elif "No se pudo extraer el token" in result.get("message", ""):
            status_code = 503 # Service Unavailable
        return jsonify(result), status_code
    return jsonify(result)

if __name__ == "__main__":
    # Activar logs de Flask para verlos en la consola localmente
    # En Render, los logs se gestionan de forma diferente pero esto ayuda localmente.
    app.logger.setLevel(os.environ.get("LOGLEVEL", "INFO").upper())
    # app.debug = False # No usar app.debug = True en producción con Gunicorn
    port = int(os.environ.get("PORT", 5000))
    # Gunicorn será el encargado de ejecutar la app en Render, no este app.run()
    # Este bloque if __name__ == "__main__": es para desarrollo local.
    # Para desarrollo local: python app.py
    app.run(host="0.0.0.0", port=port, debug=True) # debug=True para desarrollo local
