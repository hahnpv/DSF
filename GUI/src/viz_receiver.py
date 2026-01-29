
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
        # Create the plotter in a standard blocking window
        # This gives it full control of its own event loop
        gp = GlobePlotter(distinct_window=True)
        
        # Add some initial dummy data or just the globe
        # gp.add_trajectory(...) 
        
        print("3D Window Opening. Interaction should be smooth.")
        
        # Blocking call - this process stays alive until window closes
        gp.plotter.show(title="DSF 3D Visualization (Child Process)")
        
    except Exception as e:
        print(f"Viz Process Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
