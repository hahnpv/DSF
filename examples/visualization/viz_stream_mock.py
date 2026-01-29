
import sys
import os
import time
import numpy as np

# Ensure we can import from DSF if running from examples folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from python.visualization import GlobePlotter

def main():
    print("Starting Streaming Mock...")
    
    plotter = GlobePlotter()
    
    # Setup initial mock data
    # Circular orbit at 400km altitude
    R = 6378137.0 + 400000.0
    theta = 0.0
    d_theta = 0.05  # radians per step
    
    # We need to manually control the render loop for streaming
    # PyVista's show(interactive_update=True) allows this.
    plotter.plotter.show(interactive_update=True, auto_close=False)
    
    path = []
    
    try:
        while True:
            # Update Position
            theta += d_theta
            x = R * np.cos(theta)
            y = R * np.sin(theta)
            z = R * np.sin(theta * 0.5) # wobble
            
            new_point = [x, y, z]
            path.append(new_point)
            
            # Keep path length manageable for demo
            if len(path) > 200:
                path.pop(0)
            
            # Clear old actors? or update specific ones. 
            # GlobePlotter adds new meshes each time, which is inefficient for streaming.
            # Ideally we update the existing mesh points.
            # But for this simple proof of concept, removing and re-adding is "ok" provided we clean up.
            
            # Use a slightly optimized approach for 'GlobePlotter' or just call add_trajectory
            # Note: add_trajectory creates new actors. We should clear them if updating.
            plotter.plotter.clear_actors() 
            # Re-add Earth (inefficient) or better: separate dynamic vs static.
            # Since GlobePlotter.setup_earth adds a mesh, clear_actors removes it.
            # We should probably improve GlobePlotter to handle updates better.
            
            # Refactored Approach:
            # Only update the trajectory actor if possible, or just accept the flicker for now 
            # as this is a 'demo/mock' for the library capability.
            # Proper way: plotter.plotter.remove_actor('Trajectory')
            
            # For this MVP, let's just create a new GlobePlotter method for 'update_location' 
            # or handle it manually here.
            
            # Re-add earth (since we cleared)
            plotter.setup_earth()
            
            pts = np.array(path)
            plotter.add_trajectory(pts, name="LiveTraj", color="cyan")
            plotter.add_ground_track(pts, name="LiveGround", color="magenta")
            
            # Update render
            plotter.plotter.update()
            
            time.sleep(0.05)
            
    except KeyboardInterrupt:
        print("Stopping...")

if __name__ == "__main__":
    main()
