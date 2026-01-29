
import sys
import os
import argparse

# Ensure we can import from DSF if running from examples folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from python.visualization import GlobePlotter, load_csv_trajectory

def main():
    parser = argparse.ArgumentParser(description="Visualize trajectory from CSV")
    parser.add_argument("file", help="Path to CSV file (e.g. falconout.csv)")
    parser.add_argument("--texture", help="Path to earth texture image")
    args = parser.parse_args()

    # Load data
    print(f"Loading {args.file}...")
    points = load_csv_trajectory(args.file)
    
    if points is None:
        print("Failed to load data.")
        sys.exit(1)
        
    print(f"Loaded {len(points)} points.")

    # Setup Plotter
    plotter = GlobePlotter(texture_path=args.texture)
    
    # Add Trajectory (Inertial/ECEF)
    # Note: If points are ECI, they won't match the ground map unless we rotate them.
    # For this demo, we assume the user knows what frame they are plotting in.
    plotter.add_trajectory(points, name="Trajectory", color="orange", line_width=3)
    
    # Add Ground Track (Projected)
    plotter.add_ground_track(points, name="GroundTrack", color="white")
    
    print("Showing plot...")
    plotter.show()

if __name__ == "__main__":
    main()
