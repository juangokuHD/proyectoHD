"""JSON persistence for camera-specific parking-space layouts."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

CAMERA_FILE = Path(__file__).resolve().parent.parent / "data" / "parking_spaces.json"


def load_cameras() -> list[dict[str, Any]]:
    CAMERA_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not CAMERA_FILE.exists():
        return []
    with CAMERA_FILE.open(encoding="utf-8") as file:
        value = json.load(file)
    if not isinstance(value, list):
        raise ValueError("The parking-space JSON file must contain a list of cameras.")
    return value


def save_cameras(cameras: list[dict[str, Any]]) -> None:
    CAMERA_FILE.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="parking-spaces-", suffix=".json", dir=CAMERA_FILE.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(cameras, file, indent=2)
            file.write("\n")
        os.replace(temporary_name, CAMERA_FILE)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def save_camera(camera: dict[str, Any]) -> None:
    cameras = load_cameras()
    cameras = [entry for entry in cameras if entry.get("id") != camera["id"]]
    cameras.append(camera)
    save_cameras(cameras)


def delete_camera(camera_id: str) -> bool:
    cameras = load_cameras()
    remaining = [camera for camera in cameras if camera.get("id") != camera_id]
    save_cameras(remaining)
    return len(remaining) != len(cameras)