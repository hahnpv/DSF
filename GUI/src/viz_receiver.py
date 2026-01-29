
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
            while running:
                try:
                    chunk, addr = sock.recvfrom(4096)
                    # Parse immediately in thread to offload main thread? 
                    # Or just queue raw bytes? Queueing raw bytes is safer for speed.
                    data_queue.put(chunk)
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
        
        # State
        trajectory_points = []
        
        def update_viz(step_id):
            # Process up to N items from queue to avoid freezing UI if flood
            # If queue is huge, we might lag, but UI will stay responsive.
            
            items_processed = 0
            has_new_data = False
            
            while not data_queue.empty() and items_processed < 50:
                try:
                    chunk = data_queue.get_nowait()
                    try:
                        pos = json.loads(chunk.decode())
                        pt = [float(pos['x']), float(pos['y']), float(pos['z'])]
                        trajectory_points.append(pt)
                        has_new_data = True
                    except Exception as e:
                        pass # Ignore parse errors
                    items_processed += 1
                except queue.Empty:
                    break
            
            # Update Plot if we have new points
            if has_new_data and len(trajectory_points) > 2:
                # Keep tail
                limit = 2000 # Reduced limit for performance
                pts_to_plot = trajectory_points[-limit:]
                
                import numpy as np
                arr = np.array(pts_to_plot)
                gp.add_trajectory(arr, name="LiveTraj", color="cyan", line_width=4, stop_marker=True)
                gp.add_ground_track(arr, name="LiveGround", color="magenta", line_width=2)

        # Register callback to run
        # gp.plotter.add_timer_event(max_steps=2147483647, duration=33, callback=update_viz)
        
        print("3D Window Opening. Interaction should be smooth.")
        gp.plotter.show(title="DSF 3D Visualization (Child Process)", interactive_update=True)
        
        while True:
            update_viz(0)
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
