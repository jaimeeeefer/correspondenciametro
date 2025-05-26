import os
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

TOKEN_ADIF = os.environ.get("ADIF_TOKEN", "")

def obtener_horarios(codigo_estacion):
    url = (
        f"https://www.adif.es/w/{codigo_estacion}"
        "?p_p_id=servicios_estacion_ServiciosEstacionPortlet"
        "&p_p_lifecycle=2"
        "&p_p_state=normal"
        "&p_p_mode=view"
        "&p_p_resource_id=/consultarHorario"
        "&p_p_cacheability=cacheLevelPage"
        "&assetEntryId=3127062"
        f"&p_p_auth={TOKEN_ADIF}"
    )

    data = {
        "_servicios_estacion_ServiciosEstacionPortlet_searchType": "proximasSalidas",
        "_servicios_estacion_ServiciosEstacionPortlet_trafficType": "cercanias",
        "_servicios_estacion_ServiciosEstacionPortlet_numPage": 0,
        "_servicios_estacion_ServiciosEstacionPortlet_commuterNetwork": "BILBAO",
        "_servicios_estacion_ServiciosEstacionPortlet_stationCode": codigo_estacion
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0",
        "Referer": f"https://www.adif.es/w/{codigo_estacion}",
        "Origin": "https://www.adif.es"
    }

    try:
        response = requests.post(url, data=data, headers=headers)
    except Exception as e:
        return None, f"Error al hacer la petición: {e}"

    if response.status_code != 200:
        return None, f"Error HTTP {response.status_code}: {response.reason}"

    try:
        json_data = response.json()
    except Exception as e:
        return None, f"No se pudo parsear JSON: {e}"

    if "error" in json_data and json_data["error"] == True:
        return None, "Error reportado por la API de ADIF"

    return json_data, None


@app.route("/api/horarios")
def api_horarios():
    codigo = request.args.get("codigo")
    if not codigo:
        return jsonify({"error": "Falta parámetro código"}), 400

    json_data, error = obtener_horarios(codigo)
    if error:
        return jsonify({"error": error}), 500

    horarios = json_data.get("horarios", [])

    return jsonify({"horarios": horarios})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
