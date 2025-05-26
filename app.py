from flask import Flask, request, jsonify
import os
import requests
import re

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
        return None, None

    # Extraemos token p_p_auth de la página (puede variar)
    token_match = re.search(r'p_p_auth=([a-zA-Z0-9]+)', r.text)
    token = token_match.group(1) if token_match else None
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
