import os
import json
import h5py
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>DSF Cesium View</title>
  <!-- CesiumJS library from CDN -->
  <script src="https://cesium.com/downloads/cesiumjs/releases/1.114/Build/Cesium/Cesium.js"></script>
  <link href="https://cesium.com/downloads/cesiumjs/releases/1.114/Build/Cesium/Widgets/widgets.css" rel="stylesheet">
  <style>
      html, body, #cesiumContainer {
          width: 100%; height: 100%; margin: 0; padding: 0; overflow: hidden;
          background-color: #000;
          font-family: sans-serif;
      }
      #loading {
          position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
          color: white; font-size: 24px; z-index: 100;
      }
  </style>
</head>
<body>
  <div id="loading">Loading DSF Telemetry...</div>
  <div id="error-log" style="color: red; position: absolute; top: 10px; left: 10px; z-index: 200;"></div>
  <div id="cesiumContainer"></div>
  <script>
    window.onerror = function(msg, url, lineNo, columnNo, error) {
      document.getElementById('error-log').innerHTML += '<p>' + msg + ' at line ' + lineNo + '</p>';
      document.getElementById('loading').innerText = "JS Error check top left";
      return false;
    };
    
    // Suppress Ion token warnings and use default offline/free providers
    Cesium.Ion.defaultAccessToken = '';
    
    // Initialize Cesium Viewer WITHOUT Ion WorldTerrain to prevent auth hangs
    // Use OpenStreetMap for the base texture since Ion default Bing Maps are suppressed
    const viewer = new Cesium.Viewer('cesiumContainer', {
      imageryProvider: new Cesium.OpenStreetMapImageryProvider({
        url : 'https://a.tile.openstreetmap.org/'
      }),
      animation: true,
      timeline: true,
      infoBox: false,
      navigationHelpButton: false,
      baseLayerPicker: false,
      geocoder: false,
      homeButton: false,
      sceneModePicker: false
    });

    // Load the CZML stream from our local Python server
    const dataSourcePromise = Cesium.CzmlDataSource.load('/data.czml');
    viewer.dataSources.add(dataSourcePromise).then(function(ds) {
        document.getElementById('loading').style.display = 'none';
        viewer.trackedEntity = ds.entities.values[0]; // Track the first vehicle automatically
        viewer.clock.multiplier = 1.0;
    }).catch(function(error) {
        console.error(error);
        document.getElementById('loading').innerText = "Error loading telemetry";
    });
  </script>
</body>
</html>
"""

def generate_czml(input_file):
    # Determine reference epoch (just use an arbitrary recent date for playback purposes)
    EPOCH = "2024-01-01T00:00:00Z"
    
    # If passed an XML config, parse it for 3D models and locate the corresponding H5s
    h5_files_to_read = []
    models_by_vehicle = {}
    
    if input_file.endswith('.xml'):
        import xml.etree.ElementTree as ET
        try:
            tree = ET.parse(input_file)
            root = tree.getroot()
                
            # Scan for vehicles and check if they declare a 'gltf' attribute
            for vehicle in root.findall(".//vehicle"):
                vname = vehicle.get('name') or vehicle.get('id')
                if vname:
                    gltf = vehicle.get('gltf')
                    scale = float(vehicle.get('scale', 1.0))
                    if gltf:
                        # Make path relative or absolute
                        gltf_path = os.path.abspath(os.path.join(os.path.dirname(input_file), gltf))
                        models_by_vehicle[vname] = {'gltf': gltf_path, 'scale': scale}
                    
                    # Try to find H5 files by vehicle name AND by child EOM id
                    candidate_names = [vname]
                    for child in vehicle:
                        child_id = child.get('id')
                        if child_id:
                            candidate_names.append(child_id)
                    
                    for cname in candidate_names:
                        for search_dir in ['.', os.path.dirname(input_file)]:
                            h5_path = os.path.join(search_dir, f"output_{cname}.h5")
                            if os.path.exists(h5_path) and h5_path not in h5_files_to_read:
                                h5_files_to_read.append(h5_path)
                                # Map the EOM group name back to the vehicle for model assignment
                                if vname in models_by_vehicle:
                                    models_by_vehicle[cname] = models_by_vehicle[vname]
                        
        except Exception as e:
            print("Error parsing XML config for models:", e)
            
        if not h5_files_to_read:
            # Fallback: scan cwd for all output*.h5 files
            import glob
            h5_files_to_read = glob.glob("output*.h5") or glob.glob(
                os.path.join(os.path.dirname(input_file), "output*.h5"))
            if not h5_files_to_read:
                h5_files_to_read.append("output.h5")
    else:
        h5_files_to_read.append(input_file)
    
    czml = [{
        "id": "document",
        "name": "DSF Simulation",
        "version": "1.0",
        "clock": {
            "interval": EPOCH + "/" + EPOCH, # Will update this with real bounds
            "currentTime": EPOCH,
            "multiplier": 1,
            "range": "LOOP_STOP",
            "step": "SYSTEM_CLOCK_MULTIPLIER"
        }
    }]
    
    max_time = 0.0
    colors = [[255, 0, 0, 255], [0, 255, 0, 255], [0, 100, 255, 255], [255, 255, 0, 255]]
    color_idx = 0
    
    for h5_file in h5_files_to_read:
        if not os.path.exists(h5_file):
            print(f"HDF5 Telemetry file not found: {h5_file}")
            continue
            
        with h5py.File(h5_file, 'r') as f:
            for group_name in f.keys():
                g = f[group_name]
                if 'Time' not in g:
                    continue
                    
                times = g['Time'][:]
                if len(times) == 0: continue
                
                # Simple decimation if too large (e.g. cap at ~5000 points)
                stride = max(1, len(times) // 5000)
                
                t_max = times[-1]
                if t_max > max_time:
                    max_time = float(t_max)
                    
                color = colors[color_idx % len(colors)]
                color_idx += 1
                
                cartesian = []
                quaternion = []
                
                has_ecef = 'XYZ_ECEF_x' in g and 'XYZ_ECEF_y' in g and 'XYZ_ECEF_z' in g
                has_quat = 'Attitude_Quat_w' in g and 'Attitude_Quat_x' in g and 'Attitude_Quat_y' in g and 'Attitude_Quat_z' in g
                
                # Check if ECEF data is actually populated (not all zeros)
                ecef_valid = False
                if has_ecef:
                    ex = g['XYZ_ECEF_x'][:]
                    ey = g['XYZ_ECEF_y'][:]
                    ez = g['XYZ_ECEF_z'][:]
                    # ECEF positions should be ~6.3M meters from center; if max < 1000 they're likely NED zeros
                    max_mag = max(abs(ex).max(), abs(ey).max(), abs(ez).max()) if len(ex) > 0 else 0
                    ecef_valid = max_mag > 100000  # At least 100km from origin = real ECEF
                
                # Find NED columns as fallback
                ned_keys = {}
                for key in g.keys():
                    kl = key.lower()
                    if 'pos n' in kl or key.startswith('Pos N'): ned_keys['n'] = key
                    elif 'pos e' in kl or key.startswith('Pos E'): ned_keys['e'] = key
                    elif 'altitude' in kl or key.startswith('Altitude'): ned_keys['alt'] = key
                    elif 'pos d' in kl or key.startswith('Pos D'): ned_keys['d'] = key         
                
                has_ned = 'n' in ned_keys and 'e' in ned_keys and ('alt' in ned_keys or 'd' in ned_keys)
                
                if not ecef_valid and not has_ned:
                    print(f"  Skipping {group_name}: no valid ECEF or NED data")
                    continue
                    
                # NED to ECEF conversion using WGS84 reference at lat=0, lon=0
                import math
                a_wgs = 6378137.0  # WGS84 semi-major axis
                f_wgs = 1/298.257223563
                e2_wgs = 2*f_wgs - f_wgs**2
                # Reference origin: lat=0, lon=0, alt=0
                ref_lat, ref_lon = 0.0, 0.0
                sin_lat = math.sin(ref_lat)
                cos_lat = math.cos(ref_lat)
                sin_lon = math.sin(ref_lon)
                cos_lon = math.cos(ref_lon)
                
                for i in range(0, len(times), stride):
                    t = float(times[i])
                    
                    if ecef_valid:
                        cartesian.extend([t, float(ex[i]), float(ey[i]), float(ez[i])])
                    else:
                        # Convert NED to ECEF
                        north = float(g[ned_keys['n']][i])
                        east = float(g[ned_keys['e']][i])
                        if 'alt' in ned_keys:
                            alt = float(g[ned_keys['alt']][i])
                        else:
                            alt = -float(g[ned_keys['d']][i])  # D is down, altitude is up
                        
                        # Convert NED offset from ref to geodetic, then to ECEF
                        # Approximate: dLat = north/a, dLon = east/(a*cos(lat))
                        lat = ref_lat + north / a_wgs
                        lon = ref_lon + east / (a_wgs * cos_lat) if cos_lat > 1e-10 else ref_lon
                        h = alt
                        
                        # Geodetic to ECEF
                        sl = math.sin(lat)
                        cl = math.cos(lat)
                        N_r = a_wgs / math.sqrt(1 - e2_wgs * sl * sl)
                        ecef_x = (N_r + h) * cl * math.cos(lon)
                        ecef_y = (N_r + h) * cl * math.sin(lon)
                        ecef_z = (N_r * (1 - e2_wgs) + h) * sl
                        cartesian.extend([t, ecef_x, ecef_y, ecef_z])
                    
                    if has_quat:
                        # Cesium expects [x, y, z, w]
                        quaternion.extend([t, float(g['Attitude_Quat_x'][i]), float(g['Attitude_Quat_y'][i]), float(g['Attitude_Quat_z'][i]), float(g['Attitude_Quat_w'][i])])
                
                entity = {
                    "id": group_name,
                    "name": group_name,
                    "path": {
                        "material": {"solidColor": {"color": {"rgba": color}}},
                        "width": 3,
                        "leadTime": 0,
                        "trailTime": 1000,
                        "resolution": 5
                    },
                    "position": {
                        "interpolationAlgorithm": "LINEAR",
                        "interpolationDegree": 1,
                        "epoch": EPOCH,
                        "cartesian": cartesian
                    }
                }
                
                # Default visual representation: a point and a simple path
                entity["point"] = {
                    "color": {"rgba": color},
                    "pixelSize": 10
                }
                
                # Check if this group matched an XML vehicle with a GLTF model
                model_info = models_by_vehicle.get(group_name)
                
                if has_quat:
                    entity["orientation"] = {
                        "interpolationAlgorithm": "LINEAR",
                        "interpolationDegree": 1,
                        "epoch": EPOCH,
                        "unitQuaternion": quaternion
                    }
                    
                    if model_info:
                        # Serve the local GLTF model via the proxy server
                        # We URL-encode the absolute path so the browser fetches it from our local server
                        import urllib.parse
                        encoded_gltf = urllib.parse.quote(model_info['gltf'])
                        entity["model"] = {
                            "gltf": encoded_gltf,
                            "scale": model_info['scale'],
                            "minimumPixelSize": 32,
                            "maximumScale": 20000
                        }
                        # hide the point if we have a model
                        del entity["point"]
                    else:
                        # Since we have orientation but no model, assign a rudimentary box as a 3D proxy
                        entity["box"] = {
                            "dimensions": {"cartesian": [10.0, 5.0, 2.0]}, # x=length, y=width, z=height
                            "material": {"solidColor": {"color": {"rgba": color}}}
                        }
                    
                czml.append(entity)
                
    # Update clock bound
    czml[0]["clock"]["interval"] = f"{EPOCH}/2024-01-01T{int(max_time//3600):02d}:{int((max_time%3600)//60):02d}:{max_time%60:06.3f}Z"
    return json.dumps(czml)


class CesiumRequestHandler(BaseHTTPRequestHandler):
    h5_file_path = None
    
    def do_GET(self):
        parsed = urlparse(self.path)
        
        if parsed.path == '/' or parsed.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(HTML_CONTENT.encode('utf-8'))
            
        elif parsed.path == '/data.czml':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            czml_str = generate_czml(self.h5_file_path)
            self.wfile.write(czml_str.encode('utf-8'))
            
        else:
            # Fallback to local files if requested (e.g. models in future)
            file_path = unquote(parsed.path).lstrip('/')
            if os.path.exists(file_path):
                self.send_response(200)
                # rudimentary mime types
                if file_path.endswith('.gltf'): self.send_header('Content-Type', 'model/gltf+json')
                elif file_path.endswith('.glb'): self.send_header('Content-Type', 'model/gltf-binary')
                else: self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                with open(file_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()

class ReusableTCPServer(HTTPServer):
    allow_reuse_address = True

def run_cesium(input_file, port=8000):
    if not os.path.exists(input_file):
        print(f"Error: file not found: {input_file}")
        return
        
    CesiumRequestHandler.h5_file_path = input_file
    server_address = ('', port)
    httpd = ReusableTCPServer(server_address, CesiumRequestHandler)
    
    url = f"http://localhost:{port}/"
    print(f"Starting server on {url}")
    print(f"Streaming HDF5 telemetry and config from: {input_file}")
    
    # Open browser automatically
    def open_browser():
        webbrowser.open(url)
    threading.Timer(1.0, open_browser).start()
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down server...")
    finally:
        httpd.server_close()
