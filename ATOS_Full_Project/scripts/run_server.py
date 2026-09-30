"""python -m scripts.run_server   ->  http://localhost:8000"""
import uvicorn

from config import cfg

if __name__ == "__main__":
    a = cfg("app")["app"]
    uvicorn.run("server.main:app", host=a["host"], port=a["port"], reload=False)
