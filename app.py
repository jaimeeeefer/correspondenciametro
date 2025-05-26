from flask import Flask, request, jsonify
import os
import requests
import re
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

    # Si no está en inputs, buscar en enlaces o scripts (opcional)
    if not token:
        # Buscar en enlaces
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "p_p_auth=" in href:
                # extraer token del href
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

@app.route("/api/horarios")
def horarios():
    codigo = request.args.get("codigo")
    if not codigo:
        return jsonify({"error": "Falta parámetro codigo"}), 400

    url_base = f"https://www.adif.es/w/{codigo}"

    session, token = obtener_token_y_sesion(url_base)
    if not session or not token:
        return jsonify({"error": "No se pudo obtener token o sesión"}), 500

    data = {
        "_servicios_estacion_ServiciosEstacionPortlet_searchType": "proximasSalidas",
        "_servicios_estacion_ServiciosEstacionPortlet_trafficType": "cercanias",
        "_servicios_estacion_ServiciosEstacionPortlet_numPage": 0,
        "_servicios_estacion_ServiciosEstacionPortlet_commuterNetwork": "BILBAO",
        "_servicios_estacion_ServiciosEstacionPortlet_stationCode": codigo,
    }

    headers_post = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": url_base,
        "Origin": "https://www.adif.es",
    }

    url_post = f"{url_base}?p_p_resource_id=/consultarHorario&p_p_auth={token}"

    r = session.post(url_post, data=data, headers=headers_post)

    if r.status_code != 200:
        return jsonify({"error": f"Error externo: {r.status_code}"}), r.status_code

    return jsonify(r.json())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
