import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

def obtener_token_y_cookies(url_base):
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 ...",
        "Referer": url_base,
        "Origin": "https://www.adif.es"
    }
    # Hacer GET para obtener cookies y token
    r = session.get(url_base, headers=headers)
    if r.status_code != 200:
        return None, None

    # Extraer token (ejemplo, puede variar)
    # Aquí tendrías que usar regex o parsing HTML para token p_p_auth
    token = "extraccion_del_token"  

    return session, token

@app.route("/api/horarios")
def horarios():
    codigo = request.args.get("codigo", "")
    url_base = f"https://www.adif.es/w/{codigo}"

    session, token = obtener_token_y_cookies(url_base)
    if not session or not token:
        return jsonify({"error": "No se pudo obtener token o cookies"}), 500

    data = {
        "_servicios_estacion_ServiciosEstacionPortlet_searchType": "proximasSalidas",
        "_servicios_estacion_ServiciosEstacionPortlet_trafficType": "cercanias",
        "_servicios_estacion_ServiciosEstacionPortlet_numPage": 0,
        "_servicios_estacion_ServiciosEstacionPortlet_commuterNetwork": "BILBAO", # o según estación
        "_servicios_estacion_ServiciosEstacionPortlet_stationCode": codigo,
    }

    headers_post = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 ...",
        "Referer": url_base,
        "Origin": "https://www.adif.es",
    }

    r = session.post(
        url_base + "?p_p_resource_id=/consultarHorario&p_p_auth=" + token,
        data=data,
        headers=headers_post,
    )

    if r.status_code != 200:
        return jsonify({"error": f"Error externo: {r.status_code}"}), r.status_code

    return jsonify(r.json())

