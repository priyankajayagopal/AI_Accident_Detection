"""The dashboard is served by the API server (vanilla JS, no npm build):  python -m scripts.run_server  -> open http://localhost:8000"""
import webbrowser

if __name__ == "__main__":
    webbrowser.open("http://localhost:8000")
    print("Start the server first:  python -m scripts.run_server")
