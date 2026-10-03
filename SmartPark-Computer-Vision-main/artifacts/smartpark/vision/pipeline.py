from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image
from ultralytics import YOLO

from .parking_spaces import scaled_camera_spaces, vehicle_space_score


# Clases de YOLO que consideramos vehículos
VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}


# Ubicación del modelo YOLO
MODEL_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "models"
    / "yolo11n.pt"
)


_model: YOLO | None = None


def get_model() -> YOLO:
    """
    Carga el modelo YOLO una sola vez.
    """

    global _model

    if _model is None:
        print(
            "[SmartPark] Cargando modelo YOLO...",
            flush=True,
        )

        _model = YOLO(str(MODEL_PATH))

        print(
            "[SmartPark] Modelo YOLO cargado correctamente.",
            flush=True,
        )

    return _model


def _decode_image(image_base64: str) -> np.ndarray:
    """
    Convierte la imagen Base64 recibida por SmartPark
    en una imagen OpenCV.
    """

    # Algunas imágenes vienen como:
    # data:image/jpeg;base64,XXXX
    if "," in image_base64:
        image_base64 = image_base64.split(",", 1)[1]

    raw = base64.b64decode(image_base64)

    image = Image.open(
        BytesIO(raw)
    ).convert("RGB")

    frame = np.array(image)

    # RGB -> BGR para OpenCV
    frame = cv2.cvtColor(
        frame,
        cv2.COLOR_RGB2BGR,
    )

    return frame


def _vehicle_detections(
    frame: np.ndarray,
    confidence: float,
) -> list[dict[str, Any]]:
    """
    Ejecuta YOLO y obtiene únicamente vehículos.

    Se utiliza una confianza interna de 0.01 para poder
    observar también detecciones débiles en la consola.

    Después se aplica la confianza elegida desde la interfaz.
    """

    model = get_model()

    height, width = frame.shape[:2]

    print(
        f"[SmartPark] Imagen recibida: {width}x{height}",
        flush=True,
    )

    print(
        f"[SmartPark] Ejecutando YOLO con confianza={confidence}",
        flush=True,
    )

    results = model.predict(
        source=frame,
        conf=0.01,
        imgsz=1280,
        classes=list(VEHICLE_CLASSES.keys()),
        device="cpu",
        verbose=False,
    )

    detections: list[dict[str, Any]] = []

    for result in results:

        if result.boxes is None:
            continue

        for box in result.boxes:

            cls = int(
                box.cls[0].item()
            )

            score = float(
                box.conf[0].item()
            )

            coords = box.xyxy[0].tolist()

            x1, y1, x2, y2 = map(
                int,
                coords,
            )

            label = VEHICLE_CLASSES.get(
                cls,
                str(cls),
            )

            # Mostrar TODAS las detecciones de vehículos
            # para poder diagnosticar el comportamiento de YOLO.
            print(
                f"[YOLO] {label} | "
                f"confianza={score:.2%} | "
                f"box=({x1},{y1},{x2},{y2})",
                flush=True,
            )

            # Aplicar la confianza seleccionada
            # en la interfaz.
            if score < confidence:
                continue

            detections.append(
                {
                    "label": label,
                    "confidence": score,
                    "box": [
                        x1,
                        y1,
                        x2,
                        y2,
                    ],
                }
            )

    print(
        f"[SmartPark] Vehículos aceptados: "
        f"{len(detections)}",
        flush=True,
    )

    return detections


def _get_occupancy_level(
    occupancy: float,
) -> str:
    """
    Convierte el porcentaje de ocupación
    en una descripción para la interfaz.
    """

    if occupancy <= 0:
        return "Sin ocupación"

    if occupancy < 30:
        return "Baja"

    if occupancy < 70:
        return "Media"

    if occupancy < 90:
        return "Alta"

    return "Muy alta"


def analyze_image(
    image_base64: str,
    camera: dict[str, Any],
    confidence: float = 0.30,
) -> dict[str, Any]:
    """
    Analiza una imagen del estacionamiento.

    Flujo:

    Imagen
       ↓
    YOLO
       ↓
    Vehículos
       ↓
    Espacios definidos
       ↓
    Vehículo -> espacio
       ↓
    Ocupados / disponibles
       ↓
    Resultado
    """

    # --------------------------------------------------
    # 1. Decodificar imagen
    # --------------------------------------------------

    frame = _decode_image(
        image_base64
    )

    height, width = frame.shape[:2]

    # --------------------------------------------------
    # 2. Obtener espacios del estacionamiento
    # --------------------------------------------------

    spaces = scaled_camera_spaces(
        camera,
        width,
        height,
    )

    print(
        f"[SmartPark] Espacios configurados: "
        f"{len(spaces)}",
        flush=True,
    )

    # --------------------------------------------------
    # 3. Detectar vehículos
    # --------------------------------------------------

    detections = _vehicle_detections(
        frame,
        confidence,
    )

    # --------------------------------------------------
    # 4. Relacionar vehículos con espacios
    # --------------------------------------------------

    occupied_by_space: dict[
        str,
        dict[str, Any],
    ] = {}

    for detection in detections:

        best_space = None
        best_score = 0.0

        for space in spaces:

            score = vehicle_space_score(
                detection["box"],
                space["polygon"],
            )

            if score > best_score:

                best_score = score
                best_space = space

        # Un vehículo solamente puede ocupar
        # un espacio.
        if (
            best_space is not None
            and best_score >= 0.50
        ):

            space_id = best_space["id"]

            previous = occupied_by_space.get(
                space_id
            )

            # Si varios vehículos caen sobre el mismo
            # espacio, conservar el de mayor puntuación.
            if (
                previous is None
                or best_score > previous["score"]
            ):

                occupied_by_space[space_id] = {
                    "score": best_score,
                    "detection": detection,
                }

                print(
                    f"[SmartPark] "
                    f"{detection['label']} -> "
                    f"{space_id} "
                    f"(score={best_score:.2f})",
                    flush=True,
                )

    # --------------------------------------------------
    # 5. Calcular ocupación
    # --------------------------------------------------

    occupied_ids = set(
        occupied_by_space.keys()
    )

    occupied = len(
        occupied_ids
    )

    total = len(
        spaces
    )

    available = total - occupied

    occupancy = (
        occupied / total * 100
        if total > 0
        else 0.0
    )

    occupancy_level = _get_occupancy_level(
        occupancy
    )

    # --------------------------------------------------
    # 6. Crear imagen anotada
    # --------------------------------------------------

    annotated = frame.copy()

    # Dibujar espacios
    for space in spaces:

        polygon = np.array(
            [
                [
                    int(point[0]),
                    int(point[1]),
                ]
                for point in space["polygon"]
            ],
            dtype=np.int32,
        )

        is_occupied = (
            space["id"] in occupied_ids
        )

        # BGR:
        # rojo = ocupado
        # verde = disponible
        color = (
            (0, 0, 255)
            if is_occupied
            else (0, 200, 0)
        )

        cv2.polylines(
            annotated,
            [polygon],
            True,
            color,
            2,
        )

        # Centro del polígono
        center = (
            polygon.mean(
                axis=0
            ).astype(int)
        )

        cv2.putText(
            annotated,
            space["id"],
            (
                int(center[0]),
                int(center[1]),
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            2,
            cv2.LINE_AA,
        )

    # Dibujar vehículos
    for detection in detections:

        x1, y1, x2, y2 = (
            detection["box"]
        )

        cv2.rectangle(
            annotated,
            (x1, y1),
            (x2, y2),
            (255, 180, 0),
            2,
        )

        text = (
            f"{detection['label']} "
            f"{detection['confidence']:.0%}"
        )

        cv2.putText(
            annotated,
            text,
            (
                x1,
                max(
                    20,
                    y1 - 5,
                ),
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 180, 0),
            2,
            cv2.LINE_AA,
        )

    # --------------------------------------------------
    # 7. Mostrar resumen sobre la imagen
    # --------------------------------------------------

    cv2.putText(
        annotated,
        f"Vehiculos: {len(detections)}",
        (20, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        annotated,
        f"Disponibles: {available}",
        (20, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 200, 0),
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        annotated,
        f"Ocupados: {occupied}",
        (20, 90),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 0, 255),
        2,
        cv2.LINE_AA,
    )

    # --------------------------------------------------
    # 8. Convertir imagen a Base64
    # --------------------------------------------------

    rgb = cv2.cvtColor(
        annotated,
        cv2.COLOR_BGR2RGB,
    )

    output_image = Image.fromarray(
        rgb
    )

    buffer = BytesIO()

    output_image.save(
        buffer,
        format="JPEG",
        quality=90,
    )

    annotated_base64 = base64.b64encode(
        buffer.getvalue()
    ).decode("utf-8")

    # --------------------------------------------------
    # 9. Resultado final
    # --------------------------------------------------

    result = {
        "totalSpaces": total,
        "availableSpaces": available,
        "occupiedSpaces": occupied,

        "occupancyPercent": round(
        occupancy,
        1,
    ),

        "occupancyLevel": occupancy_level,

        "vehicles": detections,

    # Nombre que utiliza la versión actual de app.py
        "imageBase64": annotated_base64,

    # También conservamos este nombre por compatibilidad
        "annotatedImageBase64": annotated_base64,
        }

    print(
        "[SmartPark] RESULTADO: "
        f"{len(detections)} vehículos | "
        f"{occupied} ocupados | "
        f"{available} disponibles | "
        f"{occupancy:.1f}% ocupación | "
        f"Nivel: {occupancy_level}",
        flush=True,
    )

    return result