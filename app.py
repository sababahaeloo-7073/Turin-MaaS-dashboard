import os
import json
import urllib.request
import pandas as pd
import numpy as np
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

METRO_STATION_ORDER = [
    "Fermi", "Paradiso", "Marche", "Massaua", "Pozzo Strada", 
    "Monte Grappa", "Riva Rocci", "Spezia", "Carducci-Molinette", 
    "Dante", "Nizza", "Marconi", "Porta Nuova", "Re Umberto", 
    "Vittorio Emanuele", "XVIII Dicembre", "PrinciPessa Clotilde", 
    "Bernini", "Racconigi", "Rivarolo", "Bengasi"
]

def get_turin_boundary():
    local_file = 'torino_boundary_FeaturesToJSON.geojson'
    if os.path.exists(local_file):
        try:
            with open(local_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
            
    try:
        url = "https://nominatim.openstreetmap.org/search?city=Torino&county=Torino&state=Piemonte&country=Italy&polygon_geojson=1&format=json"
        req = urllib.request.Request(url, headers={'User-Agent': 'TurinMaaSApp/1.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            if data and len(data) > 0 and 'geojson' in data[0]:
                return {
                    "type": "FeatureCollection",
                    "features": [{
                        "type": "Feature",
                        "geometry": data[0]['geojson'],
                        "properties": {"name": "Comune di Torino"}
                    }]
                }
    except Exception as e:
        print(f"⚠️ Boundary Download Warning: {e}")
    return {"type": "FeatureCollection", "features": []}

@app.route('/api/data')
def get_data():
    try:
        csv_file = 'Turin_Metro_1000m_MaaS_Analysis.csv'
        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file)
        else:
            # Mock Fallback data if CSV missing to prevent total layout crash
            df = pd.DataFrame([
                {"station_name": "Porta Nuova", "latitude": 45.0622, "longitude": 7.6784, "maas_readiness_score": 8.2, "bike_lane_km_1000m": 12.5, "shared_bike_spots_1000m": 120, "dist_to_ztl_m": 200, "is_ztl_influenced": 1, "geoai_cluster_name": "Cluster 1: High-Density"},
                {"station_name": "Fermi", "latitude": 45.0758, "longitude": 7.5886, "maas_readiness_score": 4.5, "bike_lane_km_1000m": 3.2, "shared_bike_spots_1000m": 25, "dist_to_ztl_m": 6200, "is_ztl_influenced": 0, "geoai_cluster_name": "Cluster 3: Isolated"}
            ])

        df = df.replace([np.inf, -np.inf], np.nan).fillna(0)
        
        if 'station_name' in df.columns:
            df['station_name_clean'] = df['station_name'].astype(str).str.strip()
            order_dict = {name.lower(): idx for idx, name in enumerate(METRO_STATION_ORDER)}
            df['sort_key'] = df['station_name_clean'].str.lower().map(order_dict).fillna(999)
            df = df.sort_values('sort_key').drop(columns=['sort_key', 'station_name_clean'])

        def load_geojson(filename):
            if os.path.exists(filename):
                try:
                    with open(filename, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception:
                    pass
            return {"type": "FeatureCollection", "features": []}

        sharedbike_geojson = load_geojson('sharedbike_FeaturesToJSON.geojson')
        
        bike_spots_col = 'shared_bike_spots_1000m' if 'shared_bike_spots_1000m' in df.columns else 'shared_bike_spots'
        total_shared_spots = int(df[bike_spots_col].sum()) if bike_spots_col in df.columns else len(sharedbike_geojson.get('features', []))

        total_bike_km = round(float(df['bike_lane_km_1000m'].sum()), 1) if 'bike_lane_km_1000m' in df.columns else 0
        avg_line_maas = round(float(df['maas_readiness_score'].mean()), 2) if 'maas_readiness_score' in df.columns else 0
        
        if 'is_ztl_influenced' in df.columns:
            ztl_count = int((df['is_ztl_influenced'] == 1).sum())
        else:
            ztl_count = 0
            
        total_stations = len(df)
        ztl_coverage_pct = round((ztl_count / total_stations) * 100) if total_stations > 0 else 0

        geo_data = {
            "city_boundary": get_turin_boundary(),
            "ztl": load_geojson('ZTL_FeaturesToJSON.geojson'),
            "bikelines": load_geojson('bikeline_FeaturesToJSON.geojson'),
            "metro": load_geojson('metro_FeaturesToJSON.geojson'),
            "metroline": load_geojson('metroline_FeaturesToJSON.geojson'),
            "buffers": load_geojson('metro_Buffer10_FeaturesToJSON.geojson'),
            "sharedbike": sharedbike_geojson
        }
        
        return jsonify({
            "stations": df.to_dict(orient='records'),
            "geojson": geo_data,
            "summary_kpis": {
                "avg_line_maas": avg_line_maas,
                "total_bike_km": total_bike_km,
                "total_shared_spots": total_shared_spots,
                "ztl_coverage_pct": ztl_coverage_pct,
                "total_stations": total_stations,
                "ztl_count": ztl_count
            }
        })
    except Exception as e:
        print(f"❌ Backend Critical Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>TURIN METRO LINE 1 | GeoAI Decision-Support System</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
    
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
        body { background-color: #0b131f; color: #e2e8f0; height: 100vh; overflow: hidden; display: flex; flex-direction: column; }
        
        header { 
            background: #101926; 
            border-bottom: 1px solid #1e2d42; 
            padding: 8px 20px; 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            min-height: 54px; 
        }
        .header-left { display: flex; flex-direction: column; gap: 2px; }
        .title { font-size: 14px; font-weight: 700; color: #38bdf8; letter-spacing: 0.5px; text-transform: uppercase; }
        .author-tag { font-size: 11px; color: #94a3b8; font-weight: 400; letter-spacing: 0.3px; }
        .author-name { color: #f3f4f6; font-weight: 600; }
        
        .status-badge { background: #064e3b; color: #34d399; padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; display: flex; align-items: center; gap: 5px; }
        .status-dot { width: 6px; height: 6px; background: #34d399; border-radius: 50%; box-shadow: 0 0 8px #34d399; }

        .dashboard-container { display: grid; grid-template-columns: 310px 1fr 350px; gap: 12px; padding: 12px; height: calc(100vh - 54px); }
        .card { background: #142032; border: 1px solid #1e2f47; border-radius: 10px; padding: 12px; display: flex; flex-direction: column; justify-content: space-between; position: relative; }
        .card-title { font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 6px; display: flex; justify-content: space-between; }
        
        select { background: #0f172a; color: #f8fafc; border: 1px solid #334155; padding: 8px; border-radius: 6px; width: 100%; font-size: 13px; font-weight: 600; margin-bottom: 8px; outline: none; cursor: pointer; }
        
        .ztl-badge { padding: 8px; border-radius: 8px; font-size: 12px; font-weight: 700; text-align: center; margin: 6px 0; transition: all 0.3s ease; }
        .ztl-badge.green { background: #064e3b; color: #34d399; border: 1px solid #10b981; box-shadow: 0 0 10px rgba(16, 185, 129, 0.2); }
        .ztl-badge.red { background: #4c0519; color: #fb7185; border: 1px solid #f43f5e; box-shadow: 0 0 10px rgba(244, 63, 94, 0.2); }
        .ztl-badge.blue { background: #0c4a6e; color: #38bdf8; border: 1px solid #0284c7; }

        .kpi-val { font-size: 22px; font-weight: 700; color: #f8fafc; }
        .kpi-label { font-size: 10px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }
        
        .map-card { padding: 0; overflow: hidden; position: relative; border: 1px solid #1e2f47; min-height: 400px; }
        #map { width: 100%; height: 100%; min-height: 400px; background: #070d14; z-index: 1; }
        
        .leaflet-top { top: 65px !important; }
        
        .metro-marker-icon {
            border-radius: 50%;
            display: flex !important;
            align-items: center;
            justify-content: center;
            color: #0b131f;
            font-weight: 900;
            font-size: 11px;
            box-shadow: 0 0 8px rgba(0,0,0,0.6);
            border: 1.5px solid #ffffff;
            line-height: 1;
            user-select: none;
        }

        .map-overlay-top { position: absolute; top: 12px; left: 12px; right: 12px; z-index: 1000; background: rgba(15, 23, 42, 0.88); backdrop-filter: blur(8px); border: 1px solid #334155; border-radius: 8px; padding: 10px 16px; display: flex; justify-content: space-between; align-items: center; }
        .sim-score { font-size: 20px; font-weight: 800; color: #facc15; text-shadow: 0 0 8px rgba(250, 204, 21, 0.4); }
        
        .map-legend { position: absolute; bottom: 16px; right: 16px; z-index: 1000; background: rgba(11, 19, 31, 0.92); backdrop-filter: blur(6px); border: 1px solid #1e2d42; border-radius: 8px; padding: 10px 12px; font-size: 11px; max-width: 230px; }
        .legend-item { display: flex; align-items: center; gap: 8px; margin-bottom: 5px; color: #cbd5e1; font-weight: 500; }
        
        .legend-symbol-point { 
            width: 14px; height: 14px; border-radius: 50%; flex-shrink: 0; 
            display: flex; align-items: center; justify-content: center; 
            color: #0b131f; font-weight: 900; font-size: 8px; border: 1px solid #fff; 
        }
        .legend-symbol-line { width: 16px; height: 3px; border-radius: 1px; flex-shrink: 0; }
        .legend-symbol-poly { width: 14px; height: 10px; border-radius: 2px; flex-shrink: 0; }

        .slider-container { display: flex; align-items: center; gap: 10px; font-size: 11px; font-weight: 600; color: #cbd5e1; }
        input[type=range] { accent-color: #38bdf8; cursor: pointer; }
        
        .kpi-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 4px; }
        .mini-kpi { background: #0f172a; padding: 8px 10px; border-radius: 8px; border: 1px solid #1e293b; text-align: center; }
        
        .ai-panel { background: #1e1b4b; border: 1px solid #4338ca; border-radius: 8px; padding: 10px 12px; color: #c7d2fe; font-size: 11px; height: 100%; display: flex; flex-direction: column; }
        .ai-title { font-size: 12px; font-weight: 700; color: #f43f5e; margin-bottom: 4px; display: flex; align-items: center; gap: 6px; }
        .ai-content { overflow-y: auto; max-height: 90px; padding-right: 4px; line-height: 1.45; }
    </style>
</head>
<body>

    <header>
        <div class="header-left">
            <div class="title">TURIN METRO LINE 1: GeoAI Decision-Support System for Bike Lane Feeder Expansion & ZTL Interception</div>
            <div class="author-tag">Developed by: <span class="author-name">Saba Bahaelu Horeh</span> | Urban & Spatial Data Analyst</div>
        </div>
        <div class="status-badge"><div class="status-dot"></div> SYSTEM STATUS: OPERATIONAL</div>
    </header>

    <div class="dashboard-container">
        <!-- LEFT COLUMN -->
        <div style="display: flex; flex-direction: column; gap: 12px;">
            <div class="card" style="flex: 1;">
                <div class="card-title">STATION SELECTION & ZTL STATUS</div>
                <select id="stationSelect" onchange="onStationChange()"></select>
                
                <div class="kpi-label" id="leftMaaSLabel">Base Line Avg MaaS Score</div>
                <div class="kpi-val" id="avgMaaSLeft">0.00</div>
                
                <div id="ztlBadge" class="ztl-badge blue">🌐 Line-wide Overview Active</div>
                
                <div style="margin-top: 6px;">
                    <div class="kpi-label" id="scoreSubLabel">Selected Context Score:</div>
                    <div class="kpi-val" id="readinessScore" style="font-size: 20px; color: #38bdf8;">0.00</div>
                </div>
            </div>

            <div class="card" style="flex: 1.5;">
                <div class="card-title">ZTL INTERCEPTION MATRIX <span>•••</span></div>
                <div id="scatterPlot" style="width: 100%; height: 100%;"></div>
            </div>
        </div>

        <!-- CENTER COLUMN (MAP) -->
        <div class="card map-card">
            <div class="map-overlay-top">
                <div>
                    <span style="font-size: 11px; color: #94a3b8;">SIMULATED MaaS SCORE:</span>
                    <span class="sim-score" id="simScore">0.00</span>
                    <span style="font-size: 11px; color: #f43f5e; margin-left: 10px;">AI Policy: Intervention Active</span>
                </div>
                <div class="slider-container">
                    <span>ADD BIKE LANE KM (0-5):</span>
                    <input type="range" id="bikeSlider" min="0" max="5" step="0.5" value="1.5" oninput="updateSimulation()">
                    <span id="sliderVal">1.5 km</span>
                </div>
            </div>

            <div id="map"></div>

            <div class="map-legend">
                <div style="font-weight: 700; margin-bottom: 6px; color: #ec4899; font-size: 10px;">STATION MAAS READINESS SCORE</div>
                <div class="legend-item"><div class="legend-symbol-point" style="background:#be185d;">M</div> High Score (> 7.0)</div>
                <div class="legend-item"><div class="legend-symbol-point" style="background:#ec4899;">M</div> Good Score (6.0 - 7.0)</div>
                <div class="legend-item"><div class="legend-symbol-point" style="background:#f472b6;">M</div> Moderate Score (5.0 - 6.0)</div>
                <div class="legend-item"><div class="legend-symbol-point" style="background:#fbcfe8;">M</div> Low Score (< 5.0)</div>

                <div style="font-weight: 700; margin-top: 8px; margin-bottom: 6px; color: #94a3b8; font-size: 10px;">MAP LAYERS</div>
                <div class="legend-item"><div class="legend-symbol-poly" style="background:transparent; border:1.5px solid #ffffff;"></div> Turin Boundary (OSM)</div>
                <div class="legend-item"><div class="legend-symbol-line" style="background:#ffe500; height:3.2px;"></div> Metro Line 1</div>
                <div class="legend-item"><div class="legend-symbol-line" style="background:#00f3ff; height:2px;"></div> Dynamic Bike Lanes</div>
                <div class="legend-item"><div class="legend-symbol-point" style="background:#f97316; width:8px; height:8px; border:none;"></div> Shared Bike Spots</div>
                <div class="legend-item"><div class="legend-symbol-poly" style="background:rgba(255, 255, 255, 0.05); border:1px dashed #ffffff;"></div> 1000m Station Buffer</div>
                <div class="legend-item"><div class="legend-symbol-poly" style="background:rgba(255, 20, 147, 0.25); border:1px solid #ff007f;"></div> ZTL Boundary</div>
            </div>
        </div>

        <!-- RIGHT COLUMN -->
        <div style="display: flex; flex-direction: column; gap: 12px;">
            <div class="card" style="flex: 1.4;">
                <div class="card-title">INFRASTRUCTURE BALANCE <span>•••</span></div>
                <div id="stackedBar" style="width: 100%; height: 100%;"></div>
            </div>

            <div class="card" style="flex: 0.95;">
                <div class="card-title" id="kpiCardHeader">LINE OVERALL KPI CARDS <span>•••</span></div>
                <div class="kpi-grid">
                    <div class="mini-kpi">
                        <div class="kpi-label" id="lblKpi1">MaaS Score</div>
                        <div class="kpi-val" style="color:#34d399;" id="kpiVal1">0.0</div>
                    </div>
                    <div class="mini-kpi">
                        <div class="kpi-label" id="lblKpi2">ZTL Rate</div>
                        <div class="kpi-val" style="color:#38bdf8;" id="kpiVal2">0%</div>
                    </div>
                    <div class="mini-kpi">
                        <div class="kpi-label" id="lblKpi3">Bike Lanes</div>
                        <div class="kpi-val" style="font-size:16px;" id="kpiVal3">0 km</div>
                    </div>
                    <div class="mini-kpi">
                        <div class="kpi-label" id="lblKpi4">Shared Spots</div>
                        <div class="kpi-val" style="font-size:16px;" id="kpiVal4">0</div>
                    </div>
                </div>
            </div>

            <div class="card" style="flex: 1.05; padding: 10px;">
                <div class="card-title" style="margin-bottom: 4px;">GeoAI POLICY RECOMMENDATION PANEL <span>•••</span></div>
                <div class="ai-panel">
                    <div class="ai-title" id="aiTitle">🌐 Line-Wide Strategy</div>
                    <div class="ai-content" id="aiBody">
                        Overall Turin Metro Line 1 analysis. Select an individual station from the dropdown to review specific last-mile infrastructure recommendations.
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let globalData = null;
        let map = null;
        let bufferLayerGroup = L.layerGroup();
        let stationMarkersGroup = L.layerGroup();

        function initMap() {
            map = L.map('map', { zoomControl: false }).setView([45.0650, 7.6650], 12.5);

            L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
                maxZoom: 19, subdomains: 'abcd'
            }).addTo(map);
            
            L.control.zoom({ position: 'topleft' }).addTo(map);

            bufferLayerGroup.addTo(map);
            stationMarkersGroup.addTo(map);
            setTimeout(() => { map.invalidateSize(); }, 300);
        }

        window.onload = function() {
            initMap();
            loadDashboardData();
        };

        function loadDashboardData() {
            fetch('/api/data')
                .then(res => res.json())
                .then(data => {
                    globalData = data;
                    populateDropdown();
                    renderGeoJSONLayers();
                    onStationChange();
                })
                .catch(err => console.error("Error loading data:", err));
        }

        function populateDropdown() {
            const select = document.getElementById('stationSelect');
            select.innerHTML = '';
            
            const optAll = document.createElement('option');
            optAll.value = "ALL";
            optAll.innerText = "🌐 ALL STATIONS (Line Overview)";
            select.appendChild(optAll);

            if(globalData && globalData.stations) {
                globalData.stations.forEach(s => {
                    const opt = document.createElement('option');
                    opt.value = s.station_name;
                    opt.innerText = s.station_name;
                    select.appendChild(opt);
                });
            }
            select.value = "ALL";
        }

        function getMaaSScoreColor(score) {
            if (score >= 7.0) return '#be185d';
            if (score >= 6.0) return '#ec4899';
            if (score >= 5.0) return '#f472b6';
            return '#fbcfe8';
        }

        function renderGeoJSONLayers() {
            if(!globalData || !globalData.geojson) return;
            const g = globalData.geojson;
            
            if(g.city_boundary && g.city_boundary.features && g.city_boundary.features.length > 0) {
                L.geoJSON(g.city_boundary, {
                    style: { color: '#ffffff', weight: 1.5, opacity: 0.85, fillColor: '#ffffff', fillOpacity: 0.02 }
                }).addTo(map);
            }

            if(g.ztl && g.ztl.features && g.ztl.features.length > 0) {
                L.geoJSON(g.ztl, { 
                    style: { color: '#ff007f', fillColor: '#ff1493', fillOpacity: 0.22, weight: 1.0, opacity: 1.0 }
                }).addTo(map);
            }
            
            if(g.bikelines && g.bikelines.features && g.bikelines.features.length > 0) {
                L.geoJSON(g.bikelines, { 
                    style: { color: '#00f3ff', weight: 2.0, opacity: 1.0 }
                }).addTo(map);
            }

            if(g.metroline && g.metroline.features && g.metroline.features.length > 0) {
                L.geoJSON(g.metroline, { 
                    style: { color: '#ffe500', weight: 3.2, opacity: 0.95 } 
                }).addTo(map);
            }
            
            if(g.sharedbike && g.sharedbike.features && g.sharedbike.features.length > 0) {
                L.geoJSON(g.sharedbike, {
                    pointToLayer: (feature, latlng) => L.circleMarker(latlng, { 
                        radius: 1.2, stroke: false, fillColor: '#f97316', fillOpacity: 0.7 
                    })
                }).addTo(map);
            }

            stationMarkersGroup.clearLayers();
            if(globalData.stations) {
                globalData.stations.forEach(st => {
                    const color = getMaaSScoreColor(st.maas_readiness_score);

                    const metroIcon = L.divIcon({
                        className: 'metro-marker-icon',
                        html: `<div style="background-color: ${color}; width: 18px; height: 18px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 900; color: #000000; font-size: 10px;">M</div>`,
                        iconSize: [18, 18],
                        iconAnchor: [9, 9]
                    });

                    L.marker([st.latitude, st.longitude], { icon: metroIcon })
                      .bindTooltip(`<b>${st.station_name}</b><br>MaaS Score: ${st.maas_readiness_score}`, { permanent: false, direction: 'top' })
                      .addTo(stationMarkersGroup);
                });
            }
        }

        function onStationChange() {
            if(!globalData) return;
            const selectedVal = document.getElementById('stationSelect').value;
            const kpis = globalData.summary_kpis;

            bufferLayerGroup.clearLayers();

            if (selectedVal === "ALL") {
                map.flyTo([45.0650, 7.6650], 12.5, { duration: 1.0 });

                document.getElementById('leftMaaSLabel').innerText = "Base Line Avg MaaS Score";
                document.getElementById('avgMaaSLeft').innerText = kpis.avg_line_maas;
                document.getElementById('scoreSubLabel').innerText = "Line Overall Readiness:";
                document.getElementById('readinessScore').innerText = kpis.avg_line_maas;

                const ztlBadge = document.getElementById('ztlBadge');
                ztlBadge.className = "ztl-badge blue";
                ztlBadge.innerText = `🌐 ${kpis.ztl_coverage_pct}% ZTL Interception (${kpis.ztl_count}/${kpis.total_stations} Stations)`;

                document.getElementById('kpiCardHeader').innerText = "LINE OVERALL KPI CARDS";
                document.getElementById('lblKpi1').innerText = "Line Avg MaaS";
                document.getElementById('kpiVal1').innerText = kpis.avg_line_maas;

                document.getElementById('lblKpi2').innerText = "ZTL Coverage";
                document.getElementById('kpiVal2').innerText = kpis.ztl_coverage_pct + "%";

                document.getElementById('lblKpi3').innerText = "Total Bike Lanes";
                document.getElementById('kpiVal3').innerText = kpis.total_bike_km + " km";

                document.getElementById('lblKpi4').innerText = "Total Shared Spots";
                document.getElementById('kpiVal4').innerText = kpis.total_shared_spots;

                document.getElementById('aiTitle').innerHTML = "🌐 Metro Line 1 Strategic Overview";
                document.getElementById('aiBody').innerHTML = "Turin Metro Line 1 shows robust MaaS integration in central hubs. Select any station to view specific micro-mobility feeder recommendations.";

            } else {
                const st = globalData.stations.find(s => s.station_name === selectedVal);
                if(!st) return;

                map.flyTo([st.latitude, st.longitude], 14.5, { duration: 1.2 });

                if(globalData.geojson.buffers && globalData.geojson.buffers.features) {
                    L.geoJSON(globalData.geojson.buffers, {
                        filter: (feature) => feature.properties.name === selectedVal || feature.properties.gtfs_id === st.gtfs_id,
                        style: { color: '#ffffff', opacity: 1.0, fillColor: '#ffffff', fillOpacity: 0.05, weight: 1.8, dashArray: '5, 5' }
                    }).addTo(bufferLayerGroup);
                }

                document.getElementById('leftMaaSLabel').innerText = "Station MaaS Score";
                document.getElementById('avgMaaSLeft').innerText = st.maas_readiness_score;
                document.getElementById('scoreSubLabel').innerText = "Station Readiness Score:";
                document.getElementById('readinessScore').innerText = st.maas_readiness_score;

                const ztlBadge = document.getElementById('ztlBadge');
                if(st.is_ztl_influenced === 1) {
                    ztlBadge.className = "ztl-badge green";
                    ztlBadge.innerText = "ZTL Influenced / Buffer Zone 🟢";
                } else {
                    ztlBadge.className = "ztl-badge red";
                    ztlBadge.innerText = "Outside ZTL Impact Zone 🔴";
                }

                const stationBikeKm = (st.bike_lane_km_1000m || 0).toFixed(1);
                const stationSpots = st.shared_bike_spots_1000m !== undefined ? st.shared_bike_spots_1000m : (st.shared_bike_spots || 0);

                document.getElementById('kpiCardHeader').innerText = `STATION: ${st.station_name}`;
                document.getElementById('lblKpi1').innerText = "Station MaaS";
                document.getElementById('kpiVal1').innerText = st.maas_readiness_score;

                document.getElementById('lblKpi2').innerText = "Dist to ZTL";
                document.getElementById('kpiVal2').innerText = Math.round(st.dist_to_ztl_m) + " m";

                document.getElementById('lblKpi3').innerText = "Buffer Bike Lanes";
                document.getElementById('kpiVal3').innerText = stationBikeKm + " km";

                document.getElementById('lblKpi4').innerText = "Buffer Shared Spots";
                document.getElementById('kpiVal4').innerText = stationSpots;

                updateAIRecommendation(st);
            }

            updateSimulation();
            renderScatterPlot();
            renderStackedBar();
        }

        function updateAIRecommendation(st) {
            const title = document.getElementById('aiTitle');
            const body = document.getElementById('aiBody');

            if (st.geoai_cluster_name && String(st.geoai_cluster_name).includes("Cluster 3")) {
                title.innerHTML = "🚀 Priority Growth Corridor";
                body.innerHTML = `<b>Target: Feeder Infrastructure Expansion</b><br>Station <b>${st.station_name}</b> has high demand potential. Priority action: Construct dedicated protected bike connectors.`;
            } else if (st.is_ztl_influenced === 1) {
                title.innerHTML = "🔔 ZTL Interception Hub";
                body.innerHTML = `<b>Target: Expand E-Bike Docks (+50 spots)</b><br>Station <b>${st.station_name}</b> sits directly on the ZTL boundary. Intercept car drivers with last-mile micro-mobility.`;
            } else {
                title.innerHTML = "☀️ Balanced Transition Zone";
                body.innerHTML = `<b>Target: Network Optimization</b><br>Station <b>${st.station_name}</b> maintains balanced modal connectivity. Optimize existing bike lane signage and lighting.`;
            }
        }

        function updateSimulation() {
            const addKm = parseFloat(document.getElementById('bikeSlider').value) || 0;
            document.getElementById('sliderVal').innerText = addKm + " km";
            
            const selectedVal = document.getElementById('stationSelect').value;
            if(!globalData) return;

            if(selectedVal === "ALL") {
                let simAvg = (globalData.summary_kpis.avg_line_maas + (addKm * 0.35)).toFixed(2);
                document.getElementById('simScore').innerText = Math.min(10.0, simAvg);
            } else {
                const st = globalData.stations.find(s => s.station_name === selectedVal);
                if(st) {
                    let simScore = (st.maas_readiness_score + (addKm * 0.45)).toFixed(2);
                    document.getElementById('simScore').innerText = Math.min(10.0, simScore);
                }
            }
            renderScatterPlot();
        }

        function renderScatterPlot() {
            if (!globalData || !globalData.stations) return;

            const selectedVal = document.getElementById('stationSelect').value;
            const addKm = parseFloat(document.getElementById('bikeSlider').value) || 0;

            const cluster1 = [];
            const cluster2 = [];
            const cluster3 = [];

            globalData.stations.forEach(st => {
                const origBike = st.bike_lane_km_1000m || 0;
                const simBike = origBike + addKm;
                const distZtl = Math.round(st.dist_to_ztl_m || 0);

                const item = {
                    x: simBike,
                    y: distZtl,
                    name: st.station_name,
                    cluster: st.geoai_cluster_name || "Cluster 2: Moderate",
                    isSelected: (selectedVal !== "ALL" && st.station_name === selectedVal)
                };

                const clusterStr = String(item.cluster).toLowerCase();

                if (clusterStr.includes("1") || clusterStr.includes("high")) {
                    cluster1.push(item);
                } else if (clusterStr.includes("3") || clusterStr.includes("isolated")) {
                    cluster3.push(item);
                } else {
                    cluster2.push(item);
                }
            });

            const createClusterTrace = (dataArray, traceName, color) => ({
                x: dataArray.map(d => d.x),
                y: dataArray.map(d => d.y),
                text: dataArray.map(d => d.name),
                mode: 'markers',
                name: traceName,
                marker: {
                    size: dataArray.map(d => d.isSelected ? 14 : 11),
                    color: color,
                    symbol: 'circle',
                    opacity: dataArray.map(d => (selectedVal === "ALL" || d.isSelected) ? 1.0 : 0.35),
                    line: {
                        color: dataArray.map(d => d.isSelected ? '#ffffff' : 'transparent'),
                        width: dataArray.map(d => d.isSelected ? 2.5 : 0)
                    }
                },
                hovertemplate: '<b>%{text}</b><br>Simulated Bike Lane: %{x:.1f} km<br>Distance to ZTL: %{y} m<extra></extra>'
            });

            const traceC1 = createClusterTrace(cluster1, 'Cluster 1: High-Density', '#10b981');
            const traceC2 = createClusterTrace(cluster2, 'Cluster 2: Moderate', '#a855f7');
            const traceC3 = createClusterTrace(cluster3, 'Cluster 3: Isolated', '#f43f5e');

            const thresholdLine = {
                type: 'line',
                x0: -1,
                x1: 36,
                y0: 500,
                y1: 500,
                line: { color: '#06b6d4', width: 2.5, dash: 'dash' }
            };

            const layout = {
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent',
                margin: { l: 50, r: 15, t: 10, b: 45 },
                showlegend: true,
                legend: {
                    x: 0.35, y: 0.98,
                    xanchor: 'left', yanchor: 'top',
                    font: { color: '#ffffff', size: 12, family: 'Inter', weight: 600 },
                    bgcolor: 'transparent',
                    itemsizing: 'constant'
                },
                shapes: [thresholdLine],
                xaxis: {
                    title: { text: 'Simulated Bike Lane (km)', font: { color: '#94a3b8', size: 11, family: 'Inter' }, pad: 8 },
                    tickfont: { color: '#64748b', size: 10 },
                    gridcolor: '#1a273a',
                    zerolinecolor: '#1a273a',
                    range: [-1, 36],
                    dtick: 10
                },
                yaxis: {
                    title: { text: 'Distance to ZTL (m)', font: { color: '#94a3b8', size: 11, family: 'Inter' }, pad: 8 },
                    tickfont: { color: '#64748b', size: 10 },
                    gridcolor: '#1a273a',
                    zerolinecolor: '#1a273a',
                    range: [-300, 6800],
                    dtick: 1000
                }
            };

            Plotly.newPlot('scatterPlot', [traceC1, traceC2, traceC3], layout, { responsive: true, displayModeBar: false });
        }

        function renderStackedBar() {
            if (!globalData || !globalData.stations) return;

            const stations = globalData.stations;
            const names = stations.map(s => s.station_name);
            const bikeLanes = stations.map(s => s.bike_lane_km_1000m || 0);
            const sharedSpots = stations.map(s => s.shared_bike_spots_1000m !== undefined ? s.shared_bike_spots_1000m : (s.shared_bike_spots || 0));

            const trace1 = { x: names, y: bikeLanes, name: 'Bike Lanes (km)', type: 'bar', marker: { color: '#00f3ff' } };
            const trace2 = { x: names, y: sharedSpots, name: 'Shared Bike Spots', type: 'bar', marker: { color: '#f97316' } };

            const layout = {
                barmode: 'stack',
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent',
                margin: { l: 30, r: 10, t: 10, b: 60 },
                showlegend: true,
                legend: { x: 0, y: 1.1, orientation: 'h', font: { color: '#e2e8f0', size: 9 } },
                xaxis: { tickfont: { color: '#64748b', size: 8 }, tickangle: -45, gridcolor: '#1e2d42' },
                yaxis: { tickfont: { color: '#64748b', size: 8 }, gridcolor: '#1e2d42' }
            };

            Plotly.newPlot('stackedBar', [trace1, trace2], layout, { responsive: true, displayModeBar: false });
        }
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    app.run(debug=True, port=5000)
