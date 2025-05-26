from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

def obtener_token_y_sesion(url_base):
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": url_base,
        "Origin": "https://www.adif.es"
    }
    r = session.get(url_base, headers=headers)
    if r.status_code != 200:
        print("Error al obtener página base:", r.status_code)
        return None, None

    soup = BeautifulSoup(r.text, "html.parser")

    # Buscar token p_p_auth en inputs ocultos
    token = None
    for inp in soup.find_all("input", {"name": "p_p_auth"}):
        token = inp.get("value")
        if token:
            break

    # Si no está en inputs, buscar en enlaces
    if not token:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "p_p_auth=" in href:
                import urllib.parse as up
                qs = up.urlparse(href).query
                params = up.parse_qs(qs)
                if "p_p_auth" in params:
                    token = params["p_p_auth"][0]
                    break

    if not token:
        print("No se encontró token p_p_auth en la página.")
        return None, None

    return session, token

@app.route('/horarios')
def horarios():
    codigo_estacion = request.args.get('codigo')
    if not codigo_estacion:
        return jsonify({"error": "Falta parámetro 'codigo'"}), 400

    url_base = f"https://www.adif.es/w/{codigo_estacion}"
    session, token = obtener_token_y_sesion(url_base)
    if not token or not session:
        return jsonify({"error": "No se pudo obtener token o sesión"}), 500

    url_post = (
        f"https://www.adif.es/w/{codigo_estacion}"
        "?p_p_id=servicios_estacion_ServiciosEstacionPortlet"
        "&p_p_lifecycle=2"
        "&p_p_state=normal"
        "&p_p_mode=view"
        "&p_p_resource_id=/consultarHorario"
        "&p_p_cacheability=cacheLevelPage"
        f"&p_p_auth={token}"
    )

    data = {
        "_servicios_estacion_ServiciosEstacionPortlet_searchType": "proximasSalidas",
        "_servicios_estacion_ServiciosEstacionPortlet_trafficType": "cercanias",
        "_servicios_estacion_ServiciosEstacionPortlet_numPage": 0,
        "_servicios_estacion_ServiciosEstacionPortlet_commuterNetwork": "BILBAO",  # Aquí podrías mejorar para no hardcodear
        "_servicios_estacion_ServiciosEstacionPortlet_stationCode": codigo_estacion
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": url_base,
        "Origin": "https://www.adif.es"
    }

    resp = session.post(url_post, data=data, headers=headers)
    if resp.status_code != 200:
        return jsonify({"error": f"Error al consultar horarios: {resp.status_code}"}), resp.status_code

    try:
        result = resp.json()
    except Exception:
        return jsonify({"error": "La respuesta no es JSON válida"}), 500

    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
