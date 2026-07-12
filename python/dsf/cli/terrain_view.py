"""
dsf.cli.terrain_view
--------------------
3D terrain + trajectory visualizer.

Given an XML config file, finds the corresponding (newest) H5 output,
loads the trajectory and relevant terrain tiles, and renders an
interactive matplotlib 3D view.

Works with:
  - Submarine bathymetry (GEBCO HGT tiles)
  - Terrain-following missiles (SRTM/DTED tiles)
  - Any sim with lat/lon/alt telemetry over terrain

Usage:
    dsf terrain <xml_file>
    dsf terrain <h5_file>
    dsf terrain <h5_file> --terrain-dir /path/to/tiles
"""

import os
import sys
import glob
import struct
import argparse
import numpy as np

def find_newest_h5(xml_path: str) -> str:
    """Find the newest H5 file matching the XML basename."""
    stem = os.path.splitext(os.path.basename(xml_path))[0]
    d = os.path.dirname(os.path.abspath(xml_path))
    
    # Look for bare name first (newest by our rotation convention)
    bare = os.path.join(d, stem + ".h5")
    if os.path.exists(bare):
        return bare
    
    # Fallback: any H5 matching the stem
    candidates = glob.glob(os.path.join(d, stem + "*.h5"))
    if candidates:
        return max(candidates, key=os.path.getmtime)
    
    # Last resort: any H5 in the directory
    candidates = glob.glob(os.path.join(d, "*.h5"))
    if candidates:
        return max(candidates, key=os.path.getmtime)
    
    return None


def parse_terrain_dir_from_xml(xml_path: str) -> str:
    """Extract data_dir from <terrain> element in XML."""
    import xml.etree.ElementTree as ET
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        # Search for terrain/TerrainModel element anywhere in tree
        for elem in root.iter():
            if elem.tag.lower() in ('terrain',):
                dd = elem.get('data_dir', '')
                if dd:
                    return dd
            if elem.get('class', '') == 'TerrainModel':
                dd = elem.get('data_dir', '')
                if dd:
                    return dd
    except Exception:
        pass
    return ''


def load_hgt_tile(path: str):
    """Load an SRTM HGT file. Returns (lat_sw, lon_sw, grid, N)."""
    # Parse filename: N33W119.hgt
    fname = os.path.basename(path).upper()
    lat_sign = 1 if fname[0] == 'N' else -1
    lat_sw = lat_sign * int(fname[1:3])
    lon_sign = 1 if fname[3] == 'E' else -1
    lon_sw = lon_sign * int(fname[4:7])
    
    data = open(path, 'rb').read()
    n_samples = len(data) // 2
    N = int(np.sqrt(n_samples))
    
    vals = struct.unpack(f'>{N*N}h', data[:N*N*2])
    grid = np.array(vals, dtype=np.float64).reshape(N, N)
    
    # HGT: row 0 = north edge, row N-1 = south edge (N→S order)
    # Flip so row 0 = south edge for intuitive lat indexing
    grid = grid[::-1, :]
    
    # Replace voids (-32768) with NaN
    grid[grid < -10000] = np.nan
    
    return lat_sw, lon_sw, grid, N


def load_dted_tile(path: str):
    """Load a USGS DTED (.dt2) file. Returns (lat_sw, lon_sw, grid, N)."""
    # Parse filename: n36_w117_1arc_v3.dt2
    fname = os.path.basename(path).lower()
    parts = fname.split('_')
    lat_sign = 1 if parts[0][0] == 'n' else -1
    lat_sw = lat_sign * int(parts[0][1:])
    lon_sign = 1 if parts[1][0] == 'e' else -1
    lon_sw = lon_sign * int(parts[1][1:])
    
    N = 3601
    HEADER_SIZE = 3428
    REC_HEADER = 8
    REC_DATA = N * 2
    REC_CHECKSUM = 4
    REC_SIZE = REC_HEADER + REC_DATA + REC_CHECKSUM
    
    raw = np.frombuffer(open(path, 'rb').read(), dtype=np.uint8)
    grid = np.zeros((N, N), dtype=np.float64)
    
    for col in range(N):
        offset = HEADER_SIZE + col * REC_SIZE + REC_HEADER
        # Vectorized big-endian int16 decoding for this column
        hi = raw[offset:offset + REC_DATA:2].astype(np.int16)
        lo = raw[offset + 1:offset + REC_DATA + 1:2].astype(np.int16)
        vals = (hi << 8) | lo
        # Fix sign for negative elevations (two's complement)
        vals[vals > 8191] -= 16384
        vals[vals <= -1000] = 0
        # Store south-to-north (row 0 = south)
        grid[:, col] = vals
    
    return lat_sw, lon_sw, grid, N


def load_trajectory(h5_path: str):
    """Load lat/lon/alt (degrees/meters) from an H5 output file. Returns dict.

    Thin wrapper over the shared loader + channel resolver — takes the first
    block that has both lat and lon (channels are stored in radians;
    converted to degrees here for the terrain math).
    """
    from dsf.utils.data_loader import load_h5, find_geodetic

    _, data = load_h5(h5_path)
    for geo in find_geodetic(data).values():
        if 'lat' in geo and 'lon' in geo:
            result = {
                'lat': np.degrees(geo['lat']).flatten(),
                'lon': np.degrees(geo['lon']).flatten(),
            }
            if 'alt' in geo:
                result['alt'] = np.asarray(geo['alt']).flatten()
            return result
    return {}


def find_tiles_for_bbox(terrain_dir: str, lat_min: float, lat_max: float,
                        lon_min: float, lon_max: float):
    """Find and load all HGT/DTED tiles covering the bounding box."""
    tiles = []
    
    lat_lo = int(np.floor(lat_min))
    lat_hi = int(np.floor(lat_max))
    lon_lo = int(np.floor(lon_min))
    lon_hi = int(np.floor(lon_max))
    
    for lat in range(lat_lo, lat_hi + 1):
        for lon in range(lon_lo, lon_hi + 1):
            # Try HGT first: N33W119.hgt
            lat_c = 'N' if lat >= 0 else 'S'
            lon_c = 'E' if lon >= 0 else 'W'
            hgt_name = f"{lat_c}{abs(lat):02d}{lon_c}{abs(lon):03d}.hgt"
            hgt_path = os.path.join(terrain_dir, hgt_name)
            
            if os.path.exists(hgt_path):
                tiles.append(load_hgt_tile(hgt_path))
                continue
            
            # Try DTED: n36_w117_1arc_v3.dt2
            lat_c2 = 'n' if lat >= 0 else 's'
            lon_c2 = 'e' if lon >= 0 else 'w'
            dted_name = f"{lat_c2}{abs(lat):02d}_{lon_c2}{abs(lon):03d}_1arc_v3.dt2"
            dted_path = os.path.join(terrain_dir, dted_name)
            
            if os.path.exists(dted_path):
                tiles.append(load_dted_tile(dted_path))
                continue
            
            print(f"  [terrain] No tile for lat={lat} lon={lon}")
    
    return tiles


def run_terrain(input_file: str, terrain_dir: str = '', decimation: int = 2,
                cull_pct: float = None, z_scale: float = 1.0):
    """Main entry point for 3D terrain visualization (PyVista/VTK)."""
    import pyvista as pv
    
    # Determine H5 path
    if input_file.endswith('.h5'):
        h5_path = input_file
        xml_path = None
    else:
        xml_path = input_file
        h5_path = find_newest_h5(xml_path)
        if not h5_path:
            print(f"Error: No H5 file found for {xml_path}")
            sys.exit(1)
    
    print(f"Loading trajectory: {h5_path}")
    traj = load_trajectory(h5_path)
    
    if 'lat' not in traj or 'lon' not in traj:
        print("Error: No lat/lon data in H5 file")
        sys.exit(1)
    
    lat = traj['lat']
    lon = traj['lon']
    alt = traj.get('alt', np.zeros_like(lat))
    
    # Normalize longitude to -180..+180
    lon = ((lon + 180) % 360) - 180
    
    print(f"  Trajectory: {len(lat)} points")
    print(f"  Lat: {lat.min():.4f}° to {lat.max():.4f}°")
    print(f"  Lon: {lon.min():.4f}° to {lon.max():.4f}°")
    print(f"  Alt: {alt.min():.1f}m to {alt.max():.1f}m")
    
    # Resolve terrain directory
    if not terrain_dir and xml_path:
        terrain_dir = parse_terrain_dir_from_xml(xml_path)
    
    if not terrain_dir:
        for candidate in ['data/bathymetry/', 'data/terrain/',
                          '../../data/bathymetry/', '../../data/terrain/']:
            test = os.path.join(os.path.dirname(os.path.abspath(input_file)), candidate)
            if os.path.isdir(test):
                terrain_dir = test
                break
    
    # Load terrain tiles
    tiles = []
    if terrain_dir:
        print(f"Loading terrain from: {terrain_dir}")
        margin = 0.05
        tiles = find_tiles_for_bbox(
            terrain_dir,
            lat.min() - margin, lat.max() + margin,
            lon.min() - margin, lon.max() + margin
        )
        print(f"  Loaded {len(tiles)} tiles")
    
    # ================================================================
    #  COORDINATE CONVERSION
    # ================================================================
    lat_ref = (lat.min() + lat.max()) / 2
    lon_ref = (lon.min() + lon.max()) / 2
    m_per_deg_lat = 111320.0
    m_per_deg_lon = 111320.0 * np.cos(np.radians(lat_ref))
    
    # Trajectory in local meters
    traj_x = (lon - lon_ref) * m_per_deg_lon
    traj_y = (lat - lat_ref) * m_per_deg_lat
    traj_z = alt
    
    # Compute cull bounding box: trajectory extents grown by cull_pct
    if cull_pct is not None and cull_pct > 0:
        grow = cull_pct / 100.0
        lat_span = lat.max() - lat.min()
        lon_span = lon.max() - lon.min()
        # Enforce a minimum of ~500m so tiny trajectories don't clip to nothing
        grow_lat = max(lat_span * grow, 500.0 / m_per_deg_lat)
        grow_lon = max(lon_span * grow, 500.0 / m_per_deg_lon)
        cull_lat_min = lat.min() - grow_lat
        cull_lat_max = lat.max() + grow_lat
        cull_lon_min = lon.min() - grow_lon
        cull_lon_max = lon.max() + grow_lon
        print(f"  Cull: bbox +{cull_pct:.0f}% \u2192 lat [{cull_lat_min:.4f}\u00b0, {cull_lat_max:.4f}\u00b0]"
              f"  lon [{cull_lon_min:.4f}\u00b0, {cull_lon_max:.4f}\u00b0]")
    else:
        cull_lat_min = cull_lat_max = None
    
    # ================================================================
    #  BUILD PYVISTA SCENE
    # ================================================================
    pl = pv.Plotter(title=os.path.splitext(os.path.basename(h5_path))[0].replace('_', ' ').title())
    
    # Add terrain surfaces
    for lat_sw, lon_sw, grid, N in tiles:
        tile_lats = np.linspace(lat_sw, lat_sw + 1, N)
        tile_lons = np.linspace(lon_sw, lon_sw + 1, N)
        
        # Clip tile to cull box (or full trajectory bbox + margin)
        if cull_lat_min is not None:
            lat_mask = (tile_lats >= cull_lat_min) & (tile_lats <= cull_lat_max)
            lon_mask = (tile_lons >= cull_lon_min) & (tile_lons <= cull_lon_max)
        else:
            margin_deg = 0.08
            lat_mask = (tile_lats >= lat.min() - margin_deg) & (tile_lats <= lat.max() + margin_deg)
            lon_mask = (tile_lons >= lon.min() - margin_deg) & (tile_lons <= lon.max() + margin_deg)
        
        if not lat_mask.any() or not lon_mask.any():
            continue
        
        sub_lats = tile_lats[lat_mask][::decimation]
        sub_lons = tile_lons[lon_mask][::decimation]
        sub_grid = grid[np.ix_(lat_mask, lon_mask)][::decimation, ::decimation]
        
        ny, nx = sub_grid.shape
        LON, LAT_grid = np.meshgrid(sub_lons, sub_lats)
        
        X = (LON - lon_ref) * m_per_deg_lon
        Y = (LAT_grid - lat_ref) * m_per_deg_lat
        Z = sub_grid
        
        # Create structured grid
        terrain_grid = pv.StructuredGrid(X, Y, Z)
        terrain_grid['Elevation'] = Z.flatten(order='F')
        
        # Choose colormap based on environment
        is_underwater = np.nanmax(Z) <= 50
        cmap = 'ocean' if is_underwater else 'terrain'
        clim = [np.nanmin(Z), max(np.nanmax(Z), np.nanmin(Z) + 1)]
        
        pl.add_mesh(terrain_grid, scalars='Elevation', cmap=cmap,
                    clim=clim, lighting=True,
                    smooth_shading=True, opacity=0.9,
                    show_scalar_bar=True,
                    scalar_bar_args={'title': 'Elevation (m)',
                                      'position_x': 0.85})
    
    # Add sea level plane if there's underwater terrain
    if any(np.nanmin(grid) < 0 for _, _, grid, _ in tiles):
        x_range = [traj_x.min() - 500, traj_x.max() + 500]
        y_range = [traj_y.min() - 500, traj_y.max() + 500]
        sea = pv.Plane(center=((x_range[0]+x_range[1])/2,
                               (y_range[0]+y_range[1])/2, 0),
                       i_size=x_range[1]-x_range[0],
                       j_size=y_range[1]-y_range[0])
        pl.add_mesh(sea, color='lightcyan', opacity=0.3)
    
    # Add trajectory as a tube
    points = np.column_stack([traj_x, traj_y, traj_z])
    traj_line = pv.lines_from_points(points)
    
    # Color trajectory by time
    if 'time' in traj:
        traj_line['Time (s)'] = traj['time'][:len(points)-1]
        tube = traj_line.tube(radius=max(abs(traj_z.max() - traj_z.min()) * 0.01, 5))
        pl.add_mesh(tube, scalars='Time (s)', cmap='hot',
                    line_width=3, show_scalar_bar=False)
    else:
        tube = traj_line.tube(radius=max(abs(traj_z.max() - traj_z.min()) * 0.01, 5))
        pl.add_mesh(tube, color='red', line_width=3)
    
    # Start / end markers
    pl.add_mesh(pv.Sphere(radius=20, center=points[0]),
                color='lime', label='Start')
    pl.add_mesh(pv.Sphere(radius=20, center=points[-1]),
                color='orange', label='End')
    
    # Camera and display
    pl.add_axes()
    pl.add_legend()
    pl.enable_terrain_style()
    if z_scale != 1.0:
        pl.set_scale(xscale=1, yscale=1, zscale=z_scale)
    pl.show_grid(xlabel='East (m)', ylabel='North (m)', zlabel='Elevation (m)')
    
    print("\nVisualization ready — GPU-accelerated (VTK/OpenGL).")
    if z_scale != 1.0:
        print(f"  Z-scale: {z_scale}x vertical exaggeration")
    print("  Left-drag: rotate | Right-drag: pan | Scroll: zoom")
    pl.show()


def main():
    parser = argparse.ArgumentParser(
        description='3D terrain + trajectory visualizer (GPU-accelerated)')
    parser.add_argument('input_file', help='XML config or H5 output file')
    parser.add_argument('--terrain-dir', default='',
                       help='Path to terrain/bathymetry tile directory')
    parser.add_argument('--decimation', type=int, default=2,
                       help='Terrain grid decimation factor (default: 2)')
    parser.add_argument('--cull', type=float, nargs='?', const=50, default=None,
                       help='Cull terrain to trajectory bbox grown by percentage. Bare --cull = 50%%. --cull 75 = 75%%.')
    parser.add_argument('--z-scale', type=float, default=1.0,
                       help='Vertical exaggeration factor (default: 1.0)')
    args = parser.parse_args()
    
    run_terrain(args.input_file, args.terrain_dir, args.decimation,
                cull_pct=args.cull, z_scale=args.z_scale)


if __name__ == '__main__':
    main()

