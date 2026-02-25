
import pyvista as pv
import numpy as np
import os

EARTH_RADIUS = 6378137.0  # meters

class GlobePlotter:
    """
    A 3D visualization class for plotting trajectories around the Earth using PyVista.
    """
    def __init__(self, texture_path=None, off_screen=False, distinct_window=True, plotter=None):
        """
        Initialize the plotter.
        
        Args:
            texture_path (str): Path to a texture image (e.g. NASA Blue Marble).
                                If None, uses PyVista's default Earth example if available.
            off_screen (bool): Whether to render off-screen (for saving screenshots).
            distinct_window (bool): Whether to act as a standalone window.
            plotter (pv.Plotter): External plotter instance (e.g. QtInteractor).
        """
        if plotter is not None:
            self.plotter = plotter
        else:
            title = "DSF 3D Visualization" if distinct_window else None
            self.plotter = pv.Plotter(off_screen=off_screen, notebook=False, title=title)
        
        self.plotter.set_background("black")
        
        if texture_path is None:
            # Check for default texture in the same package directory
            default_tex = os.path.join(os.path.dirname(__file__), "land_ocean_ice_2048.jpg")
            if os.path.exists(default_tex):
                texture_path = default_tex
                print(f"Using default texture: {texture_path}")

        self.texture_path = texture_path
        
        self.setup_earth()

    def setup_earth(self):
        """Creates the Earth sphere (WGS84 Ellipsoid) and applies texture."""
        # WGS84 parameters
        a = 6378137.0  # equatorial radius (meters)
        b = 6356752.314245  # polar radius (meters)

        # Create oblate spheroid
        self.sphere = pv.ParametricEllipsoid(a, a, b)
        
        # Generate texture coordinates (UV mapping) manually
        # This fixes mirroring and seam issues by explicit control
        points = self.sphere.points
        x, y, z = points[:, 0], points[:, 1], points[:, 2]

        # Convert to spherical coordinates for UV mapping
        # Note: arctan2(y, x) returns [-pi, pi], corresponds to longitude
        longitude = np.arctan2(y, x)
        # Latitude from arcsin(z/r)
        latitude = np.arcsin(z / np.sqrt(x**2 + y**2 + z**2))

        # Normalize to [0, 1] for texture coordinates
        # u: [0, 1] maps to [-pi, pi] longitude
        u = (longitude + np.pi) / (2 * np.pi)
        # v: [0, 1] maps to [-pi/2, pi/2] latitude
        v = (latitude + np.pi/2) / np.pi
        
        # Apply texture coordinates
        self.sphere.point_data.set_array(np.column_stack([u, v]), 'Texture Coordinates')
        self.sphere.set_active_scalars('Texture Coordinates')
        # Use proper API for setting TCoords in recent PyVista/VTK
        self.sphere.GetPointData().SetTCoords(self.sphere.GetPointData().GetArray('Texture Coordinates'))

        # Load Texture
        if self.texture_path is None:
             # Default to the copied file if not specified
             self.texture_path = os.path.join(os.path.dirname(__file__), "world.topo.bathy.200412.3x5400x2700.jpg")

        texture = None
        if self.texture_path and os.path.exists(self.texture_path):
            try:
                texture = pv.read_texture(self.texture_path)
            except Exception as e:
                print(f"Error loading texture: {e}")
        
        if texture:
             self.plotter.add_mesh(self.sphere, texture=texture, smooth_shading=True, opacity=0.8)
        else:
             print("No texture found. Using blue sphere.")
             self.plotter.add_mesh(self.sphere, color="blue", smooth_shading=True, opacity=0.8)


    def add_trajectory(self, points, name="Trajectory", color="orange", line_width=2, stop_marker=True):
        """
        Adds a 3D trajectory line to the plot.
        
        Args:
            points (np.ndarray): Nx3 array of points (x, y, z) in meters.
            name (str): Label for the actor.
            color (str): Color of the line.
            line_width (float): Width of the line.
            stop_marker (bool): Whether to add a marker/sphere at the end point.
        """
        if points is None or len(points) < 2:
            return
            
        # Create spline for smoother look, or just lines
        # simple lines are faster and more accurate to the data points
        poly_line = pv.lines_from_points(points)
        
        # Render as tubes for better visibility
        self.plotter.add_mesh(poly_line, name=name, color=color, line_width=line_width, label=name, render_lines_as_tubes=True)
        
        if stop_marker:
            end_point = points[-1]
            # Marker size relative to scale, or fixed? 
            # PyVista doesn't accept radius in screen pixels easily for generic meshes,
            # so we make a sphere.
            marker_radius = EARTH_RADIUS * 0.01  # 1% of Earth radius
            marker = pv.Sphere(radius=marker_radius, center=end_point)
            self.plotter.add_mesh(marker, name=f"{name}_marker", color=color)

    def add_ground_track(self, points, name="GroundTrack", color="white", line_width=1):
        """
        Projects the points onto the Earth's surface (spherical projection) and plots them.
        Assumes the inputs are ECEF. If ECI, this will just be a geometric projection 
        (the sub-satellite point in ECI frame).
        
        Args:
            points (np.ndarray): Nx3 array of points.
        """
        if points is None or len(points) < 2:
            return

        # Normalize to unit vectors and scale to Earth Radius + small epsilon to avoid z-fighting
        norms = np.linalg.norm(points, axis=1, keepdims=True)
        # Avoid division by zero
        norms[norms == 0] = 1.0
        
        surface_points = (points / norms) * (EARTH_RADIUS * 1.001)
        
        poly_line = pv.lines_from_points(surface_points)
        self.plotter.add_mesh(poly_line, name=name, color=color, line_width=line_width, opacity=0.7)

    def show(self, auto_close=True):
        """Shows the plotter window."""
        self.plotter.show_axes()
        self.plotter.show_grid()
        self.plotter.show(auto_close=auto_close)

    def close(self):
        """Closes the plotter."""
        self.plotter.close()
