# settings_manager.py
import json
import os

DEFAULT_SETTINGS = {
    "camera_labels": [],   # if empty, labels will be auto-filled "Cam 0", etc
    "save_path": "recordings",
    "record_chunk_minutes": 5,
    "max_record_minutes": 60,
    "window_geometry": None
}

SETTINGS_FILE = "settings.json"

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # ensure keys exist
            for k, v in DEFAULT_SETTINGS.items():
                if k not in data:
                    data[k] = v
            return data
        except Exception:
            pass
    # fallback
    return DEFAULT_SETTINGS.copy()

def save_settings(data):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print("Failed to save settings:", e)
