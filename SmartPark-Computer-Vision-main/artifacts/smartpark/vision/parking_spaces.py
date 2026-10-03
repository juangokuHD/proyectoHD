from __future__ import annotations

from typing import Any


def _point_xy(point: Any) -> tuple[float, float]:
    """
    Convierte un punto guardado como:
    - {"x": 10, "y": 20}
    - [10, 20]
    - (10, 20)

    a:
    (10, 20)
    """

    if isinstance(point, dict):
        return float(point["x"]), float(point["y"])

    return float(point[0]), float(point[1])


def _polygon_points(space: dict[str, Any]) -> list[tuple[float, float]]:
    return [
        _point_xy(point)
        for point in space["polygon"]
    ]


def scale_polygon(
    polygon: list[Any],
    reference_width: int,
    reference_height: int,
    image_width: int,
    image_height: int,
) -> list[tuple[float, float]]:

    scale_x = image_width / reference_width
    scale_y = image_height / reference_height

    result = []

    for point in polygon:

        x, y = _point_xy(point)

        result.append(
            (
                x * scale_x,
                y * scale_y,
            )
        )

    return result


def scaled_camera_spaces(
    camera: dict[str, Any],
    image_width: int,
    image_height: int,
) -> list[dict[str, Any]]:

    reference_width = int(
        camera["referenceWidth"]
    )

    reference_height = int(
        camera["referenceHeight"]
    )

    result = []

    for space in camera.get("spaces", []):

        polygon = scale_polygon(
            space["polygon"],
            reference_width,
            reference_height,
            image_width,
            image_height,
        )

        result.append(
            {
                "id": space["id"],
                "polygon": polygon,
            }
        )

    return result


def point_in_polygon(
    point: tuple[float, float],
    polygon: list[tuple[float, float]],
) -> bool:

    x, y = point

    inside = False

    j = len(polygon) - 1

    for i in range(len(polygon)):

        xi, yi = polygon[i]
        xj, yj = polygon[j]

        intersects = (
            (yi > y) != (yj > y)
            and
            x < (xj - xi) * (y - yi)
            / ((yj - yi) + 1e-9)
            + xi
        )

        if intersects:
            inside = not inside

        j = i

    return inside


def vehicle_space_score(
    box: list[int],
    polygon: list[tuple[float, float]],
) -> float:

    x1, y1, x2, y2 = box

    # Punto inferior central del vehículo.
    # Es especialmente útil para estacionamientos.
    bottom_center = (
        (x1 + x2) / 2,
        y2,
    )

    if point_in_polygon(
        bottom_center,
        polygon,
    ):
        return 1.0

    # Centro del vehículo como segunda opción.
    center = (
        (x1 + x2) / 2,
        (y1 + y2) / 2,
    )

    if point_in_polygon(
        center,
        polygon,
    ):
        return 0.75

    return 0.0


def overlap_is_significant(
    vehicle_box: list[int],
    polygon: list[tuple[float, float]],
) -> bool:

    return (
        vehicle_space_score(
            vehicle_box,
            polygon,
        )
        >= 0.50
    )