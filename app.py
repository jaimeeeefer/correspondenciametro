from flask import Flask, request, jsonify, render_template
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)

def obtener_token(station_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(station_url, headers=headers)
    if response.status_code != 200:
        return None
    html = response.text
    match = re.search(r"p_p_auth=([A-Za-z0-9]+)", html)
    if match:
        return match.group(1)
    return None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/horarios")
def get_horarios():
    codigo = request.args.get("codigo")
    if not codigo:
        return jsonify({"error": "Falta el parámetro 'codigo'"}), 400

    estacion_url = f"https://www.adif.es/w/{codigo}"
    token = obtener_token(estacion_url)
    if not token:
        return jsonify({"error": "No se pudo obtener el token de autenticación"}), 500

    url = (
        f"https://www.adif.es/w/{codigo}"
        "?p_p_id=servicios_estacion_ServiciosEstacionPortlet"
        "&p_p_lifecycle=2"
        "&p_p_state=normal"
        "&p_p_mode=view"
        "&p_p_resource_id=/consultarHorario"
        "&p_p_cacheability=cacheLevelPage"
        f"&assetEntryId=3127062"
        f"&p_p_auth={token}"
    )

    data = {
        "_servicios_estacion_ServiciosEstacionPortlet_searchType": "proximasSalidas",
        "_servicios_estacion_ServiciosEstacionPortlet_trafficType": "cercanias",
        "_servicios_estacion_ServiciosEstacionPortlet_numPage": 0,
        "_servicios_estacion_ServiciosEstacionPortlet_commuterNetwork": "BILBAO",
        "_servicios_estacion_ServiciosEstacionPortlet_stationCode": codigo,
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0",
        "Referer": estacion_url,
        "Origin": "https://www.adif.es"
    }

    response = requests.post(url, data=data, headers=headers)
    if response.status_code == 200:
        try:
            result = response.json()
            return jsonify(result)
        except Exception:
            return jsonify({"error": "No se pudo decodificar la respuesta de ADIF"}), 500
    else:
        return jsonify({"error": f"Error al consultar ADIF: {response.status_code}"}), 500

if __name__ == "__main__":
    app.run(debug=True)
