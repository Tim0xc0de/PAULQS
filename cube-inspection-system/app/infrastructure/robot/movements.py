import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "robot_config.json")

def load_config():
    """Lädt die Roboter-Konfiguration aus der JSON-Datei."""
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def get_position(name: str) -> list:
    """Gibt die Gelenkpositionen für eine benannte Position zurück."""
    config = load_config()
    return config["positions"].get(name)

def get_sequence() -> list:
    """Gibt die Inspektionssequenz zurück."""
    config = load_config()
    return config["sequence"]

def get_robot_ip() -> str:
    """Gibt die Roboter-IP zurück."""
    config = load_config()
    return config["robot_ip"]

def get_gripper_speed() -> int:
    """Gibt die Greifer-Geschwindigkeit zurück."""
    config = load_config()
    return config["gripper_speed"]

def get_gripper_close_at() -> str:
    """Gibt den Step zurück, bei dem der Greifer schließen soll."""
    config = load_config()
    return config.get("gripper_close_at")

def get_gripper_open_at() -> str:
    """Gibt den Step zurück, bei dem der Greifer öffnen soll."""
    config = load_config()
    return config.get("gripper_open_at")

def get_capture_at() -> list:
    """Gibt die Steps zurück, bei denen die Kamera ein Bild machen soll."""
    config = load_config()
    val = config.get("capture_at", [])
    if isinstance(val, str):
        return [val] if val else []
    return val
