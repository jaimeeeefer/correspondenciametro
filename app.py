from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)

def get_token(station_code):
    url = f"https://www.adif.es/w/{station_code}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("Error al obtener la página:", response.status_code)
        return None
    soup = BeautifulSoup(response.text, "html.parser")
    scripts = soup.find_all("script")
    for script in scripts:
        if script.string and "p_p_auth" in script.string:
            match = re.search(r'p_p_auth=([A-Za-z0-9]+)', script.string)
            if match:
                return match.group(1)
    return None

@app.route("/api/horarios", methods=["GET"])
def horarios():
    station_code = request.args.get("codigo")
    commuter_network = request.args.get("red", "BILBAO")  # por defecto "BILBAO"

    if not station_code:
        return jsonify({"error": "Parámetro 'codigo' es obligatorio"}), 400

    token = get_token(station_code)
    if not token:
        return jsonify({"error": "No se pudo obtener el token de ADIF"}), 500

    url = (
        f"https://www.adif.es/w/{station_code}"
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
        "_servicios_estacion_ServiciosEstacionPortlet_commuterNetwork": commuter_network,
        "_servicios_estacion_ServiciosEstacionPortlet_stationCode": station_code,
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0",
        "Referer": f"https://www.adif.es/w/{station_code}",
        "Origin": "https://www.adif.es",
    }

    response = requests.post(url, data=data, headers=headers)

    if response.status_code == 200:
        try:
            result = response.json()
        except Exception:
            return jsonify({"error": "Respuesta no es JSON", "respuesta": response.text}), 500
        return jsonify(result)
    else:
        return jsonify({"error": f"Error {response.status_code}", "detalle": response.text}), response.status_code

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
