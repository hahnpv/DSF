import os
import json
import math
import struct
import h5py
import numpy as np
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
  <script src="https://cesium.com/downloads/cesiumjs/releases/1.119/Build/Cesium/Cesium.js"></script>
  <link href="https://cesium.com/downloads/cesiumjs/releases/1.119/Build/Cesium/Widgets/widgets.css" rel="stylesheet">
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
      #view-panel {
          position: absolute; top: 10px; right: 10px; z-index: 200;
          display: flex; gap: 6px;
      }
      #view-panel button {
          padding: 6px 14px; border: 1px solid rgba(255,255,255,0.4);
          border-radius: 4px; background: rgba(0,0,0,0.6); color: #fff;
          font-size: 13px; cursor: pointer; font-family: sans-serif;
      }
      #view-panel button:hover { background: rgba(60,130,200,0.7); }
      #view-panel button.active { background: rgba(60,130,200,0.9); border-color: #6cf; }
  </style>
</head>
<body>
  <div id="loading">Loading DSF Telemetry...</div>
  <div id="error-log" style="color: red; position: absolute; top: 10px; left: 10px; z-index: 200;"></div>
  <div id="view-panel">
    <button id="btn-top" class="active" onclick="setCameraMode('top')">Top</button>
    <button id="btn-side" onclick="setCameraMode('side')">Side</button>
    <button id="btn-follow" onclick="setCameraMode('follow')">Follow</button>
  </div>
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
    const viewer = new Cesium.Viewer('cesiumContainer', {
      baseLayer: false,
      animation: true,
      timeline: true,
      infoBox: false,
      navigationHelpButton: false,
      baseLayerPicker: false,
      geocoder: false,
      homeButton: false,
      sceneModePicker: false
    });
    // Add ArcGIS satellite imagery asynchronously (required for CesiumJS 1.114+)
    Cesium.ArcGisMapServerImageryProvider.fromUrl(
      'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer'
    ).then(function(provider) {
      viewer.imageryLayers.addImageryProvider(provider);
    }).catch(function(err) {
      console.warn('ArcGIS imagery failed, using default:', err);
    });

    // ---- Subsurface / underwater rendering ----
    viewer.scene.globe.depthTestAgainstTerrain = false;
    viewer.scene.fog.enabled = false;
    viewer.scene.globe.showGroundAtmosphere = false;
    // Allow camera underground (critical for underwater views!)
    viewer.scene.screenSpaceCameraController.enableCollisionDetection = false;
    // Exaggeration = 1.0 for true engineering-accurate depths
    viewer.scene.verticalExaggeration = 1.0;
    // Enable back-face rendering so globe surface is visible from below
    viewer.scene.globe.backFaceCulling = false;

    // ---- Bathymetry terrain provider ----
    fetch('/terrain/info').then(r => r.json()).then(function(info) {
      if (!info.available) { console.log('No terrain data available'); return; }
      console.log('Terrain data:', info.data_dir);
      var tileCount = 0;
      var terrainProvider = new Cesium.CustomHeightmapTerrainProvider({
        width: 32,
        height: 32,
        tilingScheme: new Cesium.GeographicTilingScheme(),
        callback: function(x, y, level) {
          tileCount++;
          if (tileCount <= 5) console.log('Terrain tile request: z=' + level + ' x=' + x + ' y=' + y);
          return fetch('/terrain/' + level + '/' + x + '/' + y + '.terrain')
            .then(function(response) { return response.arrayBuffer(); })
            .then(function(buffer) {
              var arr = new Float32Array(buffer);
              if (tileCount <= 5) {
                var min = Infinity, max = -Infinity;
                for (var i = 0; i < arr.length; i++) {
                  if (arr[i] < min) min = arr[i];
                  if (arr[i] > max) max = arr[i];
                }
                console.log('  Tile heights: min=' + min.toFixed(0) + 'm max=' + max.toFixed(0) + 'm');
              }
              return arr;
            });
        }
      });
      viewer.terrainProvider = terrainProvider;
      viewer.scene.globe.maximumScreenSpaceError = 1.5;
    }).catch(function(err) {
      console.warn('Could not load terrain info:', err);
    });

    // Prevent render errors from halting the render loop
    viewer.scene.renderError.addEventListener(function(scene, error) {
      console.warn('Render error suppressed:', error.message);
    });

    // Monkey-patch render to catch tile frustum RangeError without halting.
    const _origRender = viewer.scene.primitives.update;
    viewer.scene.primitives.update = function() {
      try { return _origRender.apply(this, arguments); }
      catch(e) { console.warn('Primitives error suppressed:', e.message); }
    };

    // ---- Camera mode system ----
    var _cameraMode = 'top';
    var _trackedEntity = null;

    function setCameraMode(mode) {
      _cameraMode = mode;
      // Update button styles
      document.querySelectorAll('#view-panel button').forEach(function(b) {
        b.classList.remove('active');
      });
      document.getElementById('btn-' + mode).classList.add('active');

      viewer.trackedEntity = undefined; // release any tracked entity

      if (mode === 'top') {
        // Restore opaque globe for overhead view
        viewer.scene.globe.show = true;
        viewer.scene.backgroundColor = Cesium.Color.BLACK;
        if (_trackedEntity) _applyTopView();
      } else {
        // For underwater views: keep globe visible (shows bathymetry terrain)
        // but use dark ocean background for areas with no terrain
        viewer.scene.globe.show = true;
        viewer.scene.backgroundColor = new Cesium.Color(0.02, 0.05, 0.15, 1.0);

        if (_trackedEntity && mode === 'follow') {
          viewer.trackedEntity = _trackedEntity;
        } else if (_trackedEntity && mode === 'side') {
          _applySideView();
        }
      }
    }

    function _applyTopView() {
      if (!_trackedEntity) return;
      var pos = _trackedEntity.position.getValue(viewer.clock.currentTime);
      if (!pos) return;
      var carto = Cesium.Cartographic.fromCartesian(pos);
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromRadians(carto.longitude, carto.latitude, 200000),
        orientation: { heading: 0, pitch: -Cesium.Math.PI_OVER_TWO, roll: 0 },
        duration: 1.5
      });
    }

    function _applySideView() {
      if (!_trackedEntity) return;
      var pos = _trackedEntity.position.getValue(viewer.clock.currentTime);
      if (!pos) return;
      var carto = Cesium.Cartographic.fromCartesian(pos);
      // Position camera 2km east of entity, at same height, looking west
      var camPos = Cesium.Cartesian3.fromRadians(
        carto.longitude + 0.02 * Math.PI / 180,  // ~2km east
        carto.latitude,
        Math.max(carto.height, -500)  // at entity depth or sea level
      );
      viewer.camera.flyTo({
        destination: camPos,
        orientation: {
          heading: Cesium.Math.toRadians(270), // look west
          pitch: 0,                             // horizontal
          roll: 0
        },
        duration: 1.5
      });
    }

    // Load the CZML stream from our local Python server
    const dataSourcePromise = Cesium.CzmlDataSource.load('/data.czml');
    viewer.dataSources.add(dataSourcePromise).then(function(ds) {
        document.getElementById('loading').style.display = 'none';
        // Store first entity for camera tracking
        var entities = ds.entities.values;
        if (entities.length > 0) {
            _trackedEntity = entities[0];
            var pos = _trackedEntity.position.getValue(viewer.clock.startTime);
            if (pos) {
                var carto = Cesium.Cartographic.fromCartesian(pos);
                viewer.camera.flyTo({
                    destination: Cesium.Cartesian3.fromRadians(carto.longitude, carto.latitude, 200000),
                    duration: 2
                });
            }
        }
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
                    
                    deck_dir = os.path.dirname(os.path.abspath(input_file))
                    for cname in candidate_names:
                        h5_path = os.path.join(deck_dir, f"output_{cname}.h5")
                        if os.path.exists(h5_path) and h5_path not in h5_files_to_read:
                            h5_files_to_read.append(h5_path)
                            if vname in models_by_vehicle:
                                models_by_vehicle[cname] = models_by_vehicle[vname]
                    
                    # Also check plain output.h5 in the deck's directory
                    plain_h5 = os.path.join(deck_dir, "output.h5")
                    if os.path.exists(plain_h5) and plain_h5 not in h5_files_to_read:
                        h5_files_to_read.append(plain_h5)
                        
        except Exception as e:
            print("Error parsing XML config for models:", e)
            
        if not h5_files_to_read:
            deck_dir = os.path.dirname(os.path.abspath(input_file))
            print(f"ERROR: No HDF5 output files found in {deck_dir}")
            print(f"  Run the sim first: dsf run {input_file} --h5")
            print(f"  Or set output=\"hdf5\" in the XML deck")
            return json.dumps([{"id": "document", "name": "Error", "version": "1.0"}])
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
    # Altitude-aware colors: base colors per entity, modified by depth later
    colors = [[255, 0, 0, 255], [0, 255, 0, 255], [0, 100, 255, 255], [255, 255, 0, 255]]
    color_idx = 0
    
    for h5_file in h5_files_to_read:
        if not os.path.exists(h5_file):
            print(f"HDF5 Telemetry file not found: {h5_file}")
            continue
            
        with h5py.File(h5_file, 'r') as f:
            # Time may be at top level or inside each group
            top_time = f['Time'][:] if 'Time' in f else None
            
            for group_name in f.keys():
                g = f[group_name]
                if not isinstance(g, h5py.Group):
                    continue  # Skip top-level datasets (Time, Depth, etc.)
                
                # Get time array: from group first, then top-level
                if 'Time' in g:
                    times = g['Time'][:]
                elif top_time is not None:
                    times = top_time
                else:
                    print(f"  Skipping {group_name}: no Time data")
                    continue
                    
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
                
                # Check for geodetic columns (Latitude + Earth Longitude in radians)
                # These are the proper geodetic position from OblateEarth/HydroEOM
                geo_keys = {}
                for key in g.keys():
                    kl = key.lower()
                    if 'latitude' in kl: geo_keys['lat'] = key
                    elif 'earth longitude' in kl: geo_keys['elon'] = key
                    elif 'altitude' in kl: geo_keys['alt'] = key
                
                has_geodetic = 'lat' in geo_keys and 'elon' in geo_keys
                
                # Find NED columns as last-resort fallback
                ned_keys = {}
                for key in g.keys():
                    kl = key.lower()
                    if 'pos n' in kl or key.startswith('Pos N'): ned_keys['n'] = key
                    elif 'pos e' in kl or key.startswith('Pos E'): ned_keys['e'] = key
                    elif 'altitude' in kl or key.startswith('Altitude'): ned_keys['alt'] = key
                    elif 'pos d' in kl or key.startswith('Pos D'): ned_keys['d'] = key         
                
                has_ned = 'n' in ned_keys and 'e' in ned_keys and ('alt' in ned_keys or 'd' in ned_keys)
                
                if not ecef_valid and not has_geodetic and not has_ned:
                    print(f"  Skipping {group_name}: no valid ECEF, geodetic, or NED data")
                    continue
                
                # Choose position source: ECEF > Geodetic > NED
                if ecef_valid:
                    pos_mode = 'ecef'
                elif has_geodetic:
                    pos_mode = 'geodetic'
                    print(f"  {group_name}: using geodetic (Latitude + Earth Longitude)")
                else:
                    pos_mode = 'ned'
                    print(f"  {group_name}: using NED fallback (ref lat=0, lon=0)")
                    
                # WGS84 constants for geodetic/NED → ECEF conversion
                a_wgs = 6378137.0
                f_wgs = 1/298.257223563
                e2_wgs = 2*f_wgs - f_wgs**2
                
                for i in range(0, len(times), stride):
                    t = float(times[i])
                    
                    if pos_mode == 'ecef':
                        cartesian.extend([t, float(ex[i]), float(ey[i]), float(ez[i])])
                    elif pos_mode == 'geodetic':
                        # Latitude and Earth Longitude are in radians
                        lat = float(g[geo_keys['lat']][i])
                        lon = float(g[geo_keys['elon']][i])
                        # Convert Earth longitude (0..2π) to standard (-π..π)
                        if lon > math.pi:
                            lon -= 2.0 * math.pi
                        alt = float(g[geo_keys['alt']][i]) if 'alt' in geo_keys else 0.0
                        
                        # Geodetic to ECEF
                        sl = math.sin(lat)
                        cl = math.cos(lat)
                        N_r = a_wgs / math.sqrt(1 - e2_wgs * sl * sl)
                        ecef_x = (N_r + alt) * cl * math.cos(lon)
                        ecef_y = (N_r + alt) * cl * math.sin(lon)
                        ecef_z = (N_r * (1 - e2_wgs) + alt) * sl
                        cartesian.extend([t, ecef_x, ecef_y, ecef_z])
                    else:
                        # NED fallback with ref at origin
                        north = float(g[ned_keys['n']][i])
                        east = float(g[ned_keys['e']][i])
                        if 'alt' in ned_keys:
                            alt = float(g[ned_keys['alt']][i])
                        else:
                            alt = -float(g[ned_keys['d']][i])
                        ref_lat, ref_lon = 0.0, 0.0
                        lat = ref_lat + north / a_wgs
                        cos_ref = math.cos(ref_lat)
                        lon = ref_lon + east / (a_wgs * cos_ref) if cos_ref > 1e-10 else ref_lon
                        h = alt
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
                    
                # Validate: skip entities with positions near Earth's center (crash Cesium)
                if len(cartesian) >= 4:
                    mag = math.sqrt(cartesian[1]**2 + cartesian[2]**2 + cartesian[3]**2)
                    if mag < 1000000:  # < 1000 km from center = inside Earth = invalid
                        print(f"  Skipping {group_name}: ECEF position too close to origin ({mag:.0f} m)")
                        continue
                
                czml.append(entity)
                
    # Update clock bound
    czml[0]["clock"]["interval"] = f"{EPOCH}/2024-01-01T{int(max_time//3600):02d}:{int((max_time%3600)//60):02d}:{max_time%60:06.3f}Z"
    return json.dumps(czml)


# ============================================================================
#  HGT Terrain Tile Server
# ============================================================================

# Cache of loaded HGT tiles: (lat, lon) -> numpy array
_hgt_tile_cache = {}
_terrain_data_dir = ''

def _load_hgt_tile(lat_sw, lon_sw):
    """Load a 1°×1° SRTM HGT tile as a numpy array.
    
    HGT files are raw big-endian int16 grids:
      - 1201×1201 (3 arc-second, SRTM3)
      - 3601×3601 (1 arc-second, SRTM1)
    Filename convention: N47W123.hgt
    """
    key = (lat_sw, lon_sw)
    if key in _hgt_tile_cache:
        return _hgt_tile_cache[key]
    
    if not _terrain_data_dir:
        return None
    
    # Build filename: N47W123.hgt
    ns = 'N' if lat_sw >= 0 else 'S'
    ew = 'E' if lon_sw >= 0 else 'W'
    name = f"{ns}{abs(lat_sw):02d}{ew}{abs(lon_sw):03d}.hgt"
    
    # Search in terrain data directory
    path = os.path.join(_terrain_data_dir, name)
    if not os.path.exists(path):
        # Try subdirectories (common SRTM layout)
        for root, dirs, files in os.walk(_terrain_data_dir):
            if name in files:
                path = os.path.join(root, name)
                break
        else:
            return None
    
    fsize = os.path.getsize(path)
    if fsize == 1201 * 1201 * 2:
        grid_size = 1201
    elif fsize == 3601 * 3601 * 2:
        grid_size = 3601
    else:
        print(f"  [terrain] Unexpected HGT size: {fsize} bytes for {path}")
        return None
    
    data = np.fromfile(path, dtype='>i2').reshape(grid_size, grid_size)
    _hgt_tile_cache[key] = data
    print(f"  [terrain] Loaded {path} ({grid_size}×{grid_size}, min={data.min()}m max={data.max()}m)")
    return data


def _sample_terrain(lat_deg, lon_deg):
    """Get elevation at a point from HGT data. Returns 0 if no data."""
    lat_sw = int(math.floor(lat_deg))
    lon_sw = int(math.floor(lon_deg))
    tile = _load_hgt_tile(lat_sw, lon_sw)
    if tile is None:
        return 0.0
    
    grid_size = tile.shape[0]
    # Fractional position within tile (0..1)
    lat_frac = lat_deg - lat_sw
    lon_frac = lon_deg - lon_sw
    
    # Row 0 = north edge, row N-1 = south edge
    row = (1.0 - lat_frac) * (grid_size - 1)
    col = lon_frac * (grid_size - 1)
    
    r0 = int(row)
    c0 = int(col)
    r1 = min(r0 + 1, grid_size - 1)
    c1 = min(c0 + 1, grid_size - 1)
    
    dr = row - r0
    dc = col - c0
    
    # Bilinear interpolation
    h = (tile[r0, c0] * (1 - dr) * (1 - dc) +
         tile[r1, c0] * dr * (1 - dc) +
         tile[r0, c1] * (1 - dr) * dc +
         tile[r1, c1] * dr * dc)
    
    return float(h)


def _serve_heightmap_tile(z, x, y, tile_size=32):
    """Generate a heightmap tile for CesiumJS.
    
    Uses CesiumJS GeographicTilingScheme:
      - Level 0: 2 columns × 1 row (each tile is 180°×180°)
      - x increases eastward, y increases southward (y=0 = north)
    Returns a binary buffer of float32 values.
    """
    # GeographicTilingScheme: n_cols = 2^(z+1), n_rows = 2^z
    n_cols = 2 ** (z + 1)
    n_rows = 2 ** z
    
    lon_min = (x / n_cols) * 360.0 - 180.0
    lon_max = ((x + 1) / n_cols) * 360.0 - 180.0
    
    # y=0 is north edge (90°), y increases southward
    lat_max = 90.0 - (y / n_rows) * 180.0
    lat_min = 90.0 - ((y + 1) / n_rows) * 180.0
    
    # Sample elevation grid
    heights = np.zeros((tile_size, tile_size), dtype=np.float32)
    for row in range(tile_size):
        lat = lat_max - (row / (tile_size - 1)) * (lat_max - lat_min)
        for col in range(tile_size):
            lon = lon_min + (col / (tile_size - 1)) * (lon_max - lon_min)
            heights[row, col] = _sample_terrain(lat, lon)
    
    return heights.tobytes()


# ============================================================================
#  HTTP Request Handler
# ============================================================================

class CesiumRequestHandler(BaseHTTPRequestHandler):
    h5_file_path = None
    
    def log_message(self, format, *args):
        # Suppress noisy request logs for terrain tiles
        if '/terrain/' in str(args[0]) if args else False:
            return
        super().log_message(format, *args)
    
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
        
        elif parsed.path == '/terrain/info':
            # Report terrain availability
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            info = {
                'available': bool(_terrain_data_dir),
                'data_dir': _terrain_data_dir,
                'cached_tiles': len(_hgt_tile_cache)
            }
            self.wfile.write(json.dumps(info).encode('utf-8'))
        
        elif parsed.path.startswith('/terrain/'):
            # Serve heightmap tiles: /terrain/{z}/{x}/{y}.terrain
            try:
                parts = parsed.path.replace('/terrain/', '').replace('.terrain', '').split('/')
                z, x, y = int(parts[0]), int(parts[1]), int(parts[2])
                tile_data = _serve_heightmap_tile(z, x, y)
                self.send_response(200)
                self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(tile_data)
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                print(f"  [terrain] Error serving tile: {e}")
            
        else:
            # Fallback to local files if requested (e.g. models)
            file_path = unquote(parsed.path).lstrip('/')
            if os.path.exists(file_path):
                self.send_response(200)
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

def run_cesium(input_file, port=8000, terrain_dir=''):
    global _terrain_data_dir
    
    if not os.path.exists(input_file):
        print(f"Error: file not found: {input_file}")
        return
    
    # Try to find terrain data directory
    if terrain_dir:
        _terrain_data_dir = os.path.abspath(terrain_dir)
    elif input_file.endswith('.xml'):
        # Parse terrain data_dir from XML deck
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(input_file)
            terrain_el = tree.getroot().find('.//terrain')
            if terrain_el is not None:
                d = terrain_el.get('data_dir', '')
                if d:
                    _terrain_data_dir = os.path.abspath(
                        os.path.join(os.path.dirname(input_file), d))
        except Exception:
            pass
    
    if _terrain_data_dir:
        print(f"Terrain data: {_terrain_data_dir}")
    else:
        print("No terrain data directory (use --terrain to specify)")
    
    CesiumRequestHandler.h5_file_path = input_file
    server_address = ('', port)

    # Kill any previous server still holding the port
    try:
        import subprocess
        result = subprocess.run(
            ['fuser', '-k', f'{port}/tcp'],
            capture_output=True, timeout=3
        )
        if result.returncode == 0:
            import time
            time.sleep(0.3)  # give OS time to release the socket
            print(f"Killed previous process on port {port}")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # fuser not available or timed out — proceed anyway

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
