import subprocess
import os

def start_ui():
    print("Starting Streamlit UI...")
    try:
        # Run streamlit app
        subprocess.run(["streamlit", "run", "ui/app.py"])
    except KeyboardInterrupt:
        print("Stopping...")

if __name__ == "__main__":
    if not os.path.exists("data_cache"):
        os.makedirs("data_cache")
    start_ui()
