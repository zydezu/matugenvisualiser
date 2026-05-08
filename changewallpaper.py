import configparser
import shutil
import subprocess
from pathlib import Path


def change_wallpaper(path: str) -> dict:
    expanded = str(Path(path).expanduser())
    if not Path(expanded).exists():
        return {"error": f"File not found: {path}"}

    if not shutil.which("swaybg"):
        return {"error": "swaybg not found — is it installed and on your PATH?"}

    try:
        r = subprocess.run(["pgrep", "swaybg"], capture_output=True)
        if r.returncode == 0:
            subprocess.run(["pkill", "swaybg"], capture_output=True)

        subprocess.Popen(
            ["swaybg", "-i", expanded, "-m", "fill"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return {"success": f"Wallpaper set to {expanded} using swaybg"}
    except Exception as e:
        return {"error": str(e)}


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
