import configparser
import shutil
import subprocess
import time
from pathlib import Path


def change_wallpaper(path: str) -> dict:
    expanded = str(Path(path).expanduser())
    if not Path(expanded).exists():
        return {"error": f"File not found: {path}"}
    if not shutil.which("swaybg"):
        return {"error": "swaybg not found"}

    time.sleep(0.2)

    proc = subprocess.Popen(
        ["swaybg", "-i", expanded, "-m", "fill"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        start_new_session=True,  # detach from Python process
    )
    time.sleep(0.2)
    if proc.poll() is not None:
        err = proc.stderr.read().decode().strip()
        return {"error": f"swaybg exited: {err}"}
    return {"success": f"Wallpaper set to {expanded}"}


def set_waypaper_wallpaper(path: str) -> dict:
    expanded = str(Path(path).expanduser())
    if not Path(expanded).exists():
        return {"error": f"File not found: {path}"}

    config_path = Path.home() / ".config" / "waypaper" / "config.ini"
    if not config_path.exists():
        return {"error": f"waypaper config not found at {config_path}"}

    config = configparser.ConfigParser()
    config.read(str(config_path))
    if "Settings" not in config:
        config["Settings"] = {}
    config["Settings"]["wallpaper"] = path
    config["Settings"]["show_path_in_tooltip"] = "True"

    with open(config_path, "w") as f:
        config.write(f)

    return {"success": f"waypaper config updated — wallpaper set to {path}"}
