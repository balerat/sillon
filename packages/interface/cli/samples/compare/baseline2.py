import time
import subprocess
from pathlib import Path
from contextlib import contextmanager

import simplypy as sp
from simplypy.api import force_dump

CURRENT_PATH = Path(__file__).parent.resolve()

@contextmanager
def background_server():
    """Starts the background server and ensures it shuts down afterward."""
    print("\n[SETUP] Starting background SimplyCore server...")
    server_process = subprocess.Popen(["simply-server-daemon"])
    time.sleep(2)  
    try:
        yield
    finally:
        print("\n[TEARDOWN] Shutting down server...")
        server_process.terminate()
        server_process.wait()

def main():
    sp.init(
        run_name="Apollo_11_Tuned",
        project_name="Moon_Landing",
        author="Neil",
        organisation="NASA",
        project_path=str(CURRENT_PATH)
    )

    sp.log_param("learning_rate", 0.005) # ~ Changed
    sp.log_param("batch_size", 64)       # ~ Changed
    sp.log_param("optimizer", "Adam")    # = Identical
    sp.log_param("dropout", 0.2)         # + Added

    sp.add_metadata({"os": "linux", "python_version": "3.11"}) # ~ Changed
    sp.add_note("Tuned learning rate and added dropout to fix divergence.")
    sp.add_tag("tuned")

    @sp.track(save_result=True)
    def calculate_trajectory(velocity, angle):
        time.sleep(0.2) 
        return velocity * angle * 0.45  # Logic changed!

    calculate_trajectory(1200, 42)
    sp.log_result(final_loss=0.15, accuracy=0.96)

    force_dump()
    time.sleep(0.5)
    print("[SUCCESS] Tuned run saved.")

if __name__ == "__main__":
    # Wrap the whole execution in the server manager!
    with background_server():
        main()
