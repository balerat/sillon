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
    time.sleep(2)  # Give the server time to bind to the TCP port
    try:
        yield
    finally:
        print("\n[TEARDOWN] Shutting down server...")
        server_process.terminate()
        server_process.wait()

def main():
    # 1. Initialize the run
    sp.init(
        run_name="Apollo_11_Baseline",
        project_name="Moon_Landing",
        author="Neil",
        organisation="NASA",
        project_path=str(CURRENT_PATH)
    )

    sp.log_param("learning_rate", 0.01)
    sp.log_param("batch_size", 32)
    sp.log_param("optimizer", "Adam")
    sp.log_param("solver", "OpenFOAM")

    sp.add_metadata({"os": "linux", "python_version": "3.10"})
    sp.add_note("Initial baseline run for trajectory calculation.")
    sp.add_tag("baseline")

    @sp.track(save_result=True)
    def calculate_trajectory(velocity, angle):
        time.sleep(0.2) 
        return velocity * angle * 0.5

    calculate_trajectory(1000, 45)
    sp.log_result(final_loss=0.50, accuracy=0.85)

    force_dump()
    time.sleep(0.5) # Buffer to let the DB write finish before we kill the server
    print("[SUCCESS] Baseline run saved.")

if __name__ == "__main__":
    # Wrap the whole execution in the server manager!
    with background_server():
        main()
