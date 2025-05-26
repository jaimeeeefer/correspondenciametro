import os
import requests
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# Función para obtener horarios (proxy a ADIF)
def get_horarios_proxy(cod_estacion):
    # Ejemplo muy básico, ajusta según tu código real y token
    url = f"https://www.adif.es/w/{cod_estacion}?p_p_id=servicios_estacion_ServiciosEstacionPortlet&p_p_lifecycle=2&p_p_state=normal&p_p_mode=view&p_p_resource_id=/consultarHorario&p_p_cacheability=cacheLevelPage&assetEntryId=3127062&p_p_auth=TU_TOKEN_AQUI"

    data = {
        "_servicios_estacion_ServiciosEstacionPortlet_searchType": "proximasSalidas",
        "_servicios_estacion_ServiciosEstacionPortlet_trafficType": "cercanias",
        "_servicios_estacion_ServiciosEstacionPortlet_numPage": 0,
        "_servicios_estacion_ServiciosEstacionPortlet_commuterNetwork": "BILBAO",
        "_servicios_estacion_ServiciosEstacionPortlet_stationCode": cod_estacion
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0",
        "Referer": f"https://www.adif.es/w/{cod_estacion}",
        "Origin": "https://www.adif.es"
    }

    response = requests.post(url, data=data, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": True, "message": f"HTTP {response.status_code}"}

# Ruta para consultar horarios via API proxy
@app.route("/api/horarios/<cod_estacion>")
def api_horarios(cod_estacion):
    result = get_horarios_proxy(cod_estacion)
    return jsonify(result)

# Página simple para buscar horarios
@app.route("/")
def index():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>Consulta horarios ADIF</title>
</head>
<body>
    <h1>Consulta horarios de trenes ADIF</h1>
    <form id="searchForm">
        Código estación: <input type="text" id="stationCode" required>
        <button type="submit">Buscar</button>
    </form>
    <ul id="results"></ul>
    <script>
        document.getElementById('searchForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const code = document.getElementById('stationCode').value;
            const res = await fetch(`/api/horarios/${code}`);
            const data = await res.json();
            const results = document.getElementById('results');
            results.innerHTML = '';
            if(data.error) {
                results.innerHTML = `<li>Error: ${data.message || 'No hay datos'}</li>`;
                return;
            }
            if(!data.horarios || data.horarios.length === 0) {
                results.innerHTML = '<li>No hay horarios disponibles.</li>';
                return;
            }
            data.horarios.forEach(h => {
                results.innerHTML += `<li>${h.hora} - ${h.estacion} - Tren: ${h.tren}</li>`;
            });
        });
    </script>
</body>
</html>
""")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
