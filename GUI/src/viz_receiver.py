
import sys
import os
import signal

# Add repository root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from python.visualization.globe import GlobePlotter

def main():
    print("Starting 3D Viz Process...")
    
    # Handle clean exit on SIGINT/SIGTERM
    def signal_handler(sig, frame):
        print("Viz Process exiting...")
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Create UDP Socket
        import socket
        import json
        import threading
        import queue
        import time
        
        UDP_IP = "127.0.0.1"
        UDP_PORT = 5556
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Allow tracking port reuse immediately
        
        try:
            sock.bind((UDP_IP, UDP_PORT))
            print(f"Listening for UDP data on {UDP_IP}:{UDP_PORT}")
        except OSError:
            print(f"Error: Port {UDP_PORT} already in use. Is another viz process running?")
            sys.exit(1)
            
        sock.settimeout(0.5) # Non-blocking with timeout for thread loop

        # Data Queue for thread safety
        data_queue = queue.Queue()
        running = True

        def receiver_loop():
            first_packet = True # Initialize for logging
            while running:
                try:
                    # UDP limit is theoretically 65535. 
                    # With 30+ satellites, JSON can easily exceed 4KB.
                    chunk, addr = sock.recvfrom(65535)
                    # Parse immediately in thread to offload main thread? 
                    # Or just queue raw bytes? Queueing raw bytes is safer for speed.
                    data_str = chunk.decode('utf-8')
                    positions = json.loads(data_str)
                    
                    if first_packet:
                         print(f"Viz Receiver: First packet received ({len(chunk)} bytes). Vehicles: {len(positions)}", flush=True)
                         print(f"Viz Receiver: Vehicle Keys: {list(positions.keys())}", flush=True)
                         first_packet = False
                    
                    data_queue.put(positions)
                except socket.timeout:
                    continue
                except Exception as e:
                    if running: print(f"Socket Error: {e}")
                    break
        
        # Start receiver thread
        recv_thread = threading.Thread(target=receiver_loop, daemon=True)
        recv_thread.start()

        # Create the plotter
        gp = GlobePlotter(distinct_window=True)
        
        # Set initial wide view to see MEO/GEO orbits
        # Earth Radius ~6378 km. GPS ~26500 km radius.
        # 5x Radius ensures we see everything comfortably.
        R_EARTH = 6378137.0
        gp.plotter.camera_position = [(10 * R_EARTH, 0, 0), (0, 0, 0), (0, 0, 1)]
        
        # State
        trajectories = {} # {id: [[x,y,z], ...]}
        
        # Color palette for distinct vehicles
        colors = ["cyan", "magenta", "orange", "lime", "yellow", "white", "red", "blue"]
        
        def update_viz(step_id):
            # Process up to N items from queue to avoid freezing UI if flood
            items_processed = 0
            has_new_data = False
            
            while not data_queue.empty() and items_processed < 50:
                try:
                    data = data_queue.get_nowait()
                    try:
                        # data is already a dict from receiver_loop
                        # data = json.loads(chunk.decode()) 
                        
                        # Check for commands
                        if "command" in data:
                            if data["command"] == "reset":
                                print("Viz Receiver: Resetting trajectories.")
                                trajectories.clear()
                                # Also clear existing actors from plotter?
                                # PyVista actors persist. We need to clear them.
                                # GlobePlotter doesn't expose a clear method on `gp`.
                                # We can clear the plot and re-add earth? Or just let them fade?
                                # Actually `gp.add_trajectory` returns an actor name?
                                # If we clear `trajectories`, the next `update_viz` loop won't draw lines.
                                # But PyVista retains the actors in the scene until removed.
                                # We need to remove them.
                                # We can iterate over `gp.plotter.actors` and remove those starting with "Traj_".
                                actors_to_remove = [name for name in gp.plotter.actors if name.startswith("Traj_")]
                                for name in actors_to_remove:
                                    gp.plotter.remove_actor(name)
                                has_new_data = False # Don't update this frame
                                
                        # Handle both single object (legacy) and dict of vehicles
                        elif "x" in data and "y" in data:
                             # Legacy single vehicle
                             packets = {"Vehicle": data}
                        else:
                             packets = data
                             
                        if "command" not in data:
                            for vid, pos in packets.items():
                             if vid not in trajectories:
                                 trajectories[vid] = []
                             
                             pt = [float(pos['x']), float(pos['y']), float(pos['z'])]
                             trajectories[vid].append(pt)
                             
                             # Keep tail limit per vehicle
                             if len(trajectories[vid]) > 2000:
                                 trajectories[vid].pop(0)

                        has_new_data = True
                    except Exception as e:
                        print(f"Parse error: {e}", flush=True)
                        pass
                    items_processed += 1
                except queue.Empty:
                    break
            
            # Debug: print status periodically
            if step_id % 300 == 0 and trajectories:
                 # Print occasionally to show it's alive, but not spam
                 print(f"Viz Debug: {len(trajectories)} satellites tracking. Frame {step_id}", flush=True)
            
            # Update Plot if we have new points
            if has_new_data:
                import numpy as np
                color_idx = 0
                for vid, points in trajectories.items():
                    if len(points) > 2:
                        arr = np.array(points)
                        # Assign color based on simple hash or index
                        c = colors[color_idx % len(colors)]
                        
                        gp.add_trajectory(arr, name=f"Traj_{vid}", color=c, line_width=2, stop_marker=True)
                        gp.add_ground_track(arr, name=f"Gnd_{vid}", color=c, line_width=1) 
                        color_idx += 1

        # Register callback to run
        # gp.plotter.add_timer_event(max_steps=2147483647, duration=33, callback=update_viz)
        
        print("3D Window Opening. Interaction should be smooth.")
        gp.plotter.show(title="DSF 3D Visualization (Child Process)", interactive_update=True)
        
        step_counter = 0
        while True:
            update_viz(step_counter)
            step_counter += 1
            gp.plotter.update()
            time.sleep(0.01) # ~100 FPS cap, keeps CPU usage sane
            if gp.plotter.render_window.GetGenericDisplayId() == None: # Check if window closed
                break
        
    except Exception as e:
        print(f"Viz Process Error: {e}")
    finally:
        running = False # Stop thread
        if 'sock' in locals():
            sock.close()

if __name__ == "__main__":
    main()
