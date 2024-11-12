from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
import json
from pydantic import BaseModel

app = FastAPI()

LOG_DIR = Path("logs")
CONFIG_FILE = Path("config.json")
ANGULAR_STATIC_DIR = Path("static")

LOG_DIR.mkdir(exist_ok=True)
ANGULAR_STATIC_DIR.mkdir(exist_ok=True)


class ConfigData(BaseModel):
    enabled: bool


# list log files
@app.get("/logs")
async def list_logs():
    logs = [log.name for log in LOG_DIR.glob("*.log")]
    return JSONResponse(logs)


# return log file content
@app.get("/logs/{log_file}")
async def read_log(log_file: str):
    if log_file == "today":
        log_file = datetime.now().strftime("%Y-%m-%d")
    elif log_file == "yesterday":
        log_file = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    if not log_file.endswith(".log"):
        log_file += ".log"
    log_path = LOG_DIR / log_file
    if not log_path.exists() or not log_path.is_file():
        raise HTTPException(status_code=404, detail="Log file not found")
    return FileResponse(log_path)


# return config file
@app.get("/config")
async def get_config():
    if not CONFIG_FILE.exists():
        raise HTTPException(status_code=404, detail="Config file not found")
    with open(CONFIG_FILE, "r") as file:
        config_data = json.load(file)
    return JSONResponse(config_data)


# set enabled flag in config file
@app.patch("/config/enabled")
async def update_enabled(payload: ConfigData):
    if not CONFIG_FILE.exists():
        raise HTTPException(status_code=404, detail="Config file not found")
    with open(CONFIG_FILE, "r") as file:
        config = json.load(file)

    config["enabled"] = payload.enabled

    with open(CONFIG_FILE, "w") as file:
        json.dump(config, file, indent=4)

    return JSONResponse({"message": f"'enabled' set to {payload.enabled}"})


# anything else is served statically from static dir
@app.get("/{file_path:path}")
async def serve_static(file_path: str):
    static_file = ANGULAR_STATIC_DIR / file_path
    if not static_file.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(static_file)
