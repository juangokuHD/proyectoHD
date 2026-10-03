import json
import cv2

from vision.pipeline import _vehicle_detections
from vision.parking_spaces import scaled_camera_spaces, overlap_is_significant


print("=" * 70)
print("PRUEBA COMPLETA DE OCUPACION")
print("=" * 70)

# ---------------------------------------------------------
# 1. Cargar cámaras
# ---------------------------------------------------------

with open(
    "data/parking_spaces.json",
    "r",
    encoding="utf-8"
) as file:
    cameras = json.load(file)

print(f"\nCámaras encontradas: {len(cameras)}")

for camera in cameras:
    print(
        f"- {camera['name']} | "
        f"{camera['referenceWidth']}x{camera['referenceHeight']} | "
        f"{len(camera['spaces'])} espacios"
    )


# ---------------------------------------------------------
# 2. Seleccionar cámara de 14 espacios
# ---------------------------------------------------------

camera = next(
    camera
    for camera in cameras
    if len(camera["spaces"]) == 14
)

print("\nCámara utilizada:")
print(camera["name"])

print(
    "Referencia:",
    camera["referenceWidth"],
    "x",
    camera["referenceHeight"]
)


# ---------------------------------------------------------
# 3. Cargar imagen
# ---------------------------------------------------------

image = cv2.imread("bus.jpg")

if image is None:
    raise RuntimeError("No se pudo abrir bus.jpg")

height, width = image.shape[:2]

print("\nImagen:")
print(f"{width} x {height}")


# ---------------------------------------------------------
# 4. Detectar vehículos
# ---------------------------------------------------------

print("\nDetectando vehículos...")

vehicles = _vehicle_detections(
    image,
    0.05
)

print(
    f"Vehículos encontrados: {len(vehicles)}"
)

for vehicle in vehicles:

    print(
        f"  {vehicle['label']} "
        f"{vehicle['confidence']:.2%} "
        f"box={vehicle['box']}"
    )


# ---------------------------------------------------------
# 5. Escalar espacios
# ---------------------------------------------------------

spaces = scaled_camera_spaces(
    camera,
    width,
    height
)

print(
    f"\nEspacios escalados: {len(spaces)}"
)


# ---------------------------------------------------------
# 6. Comparar vehículos contra espacios
# ---------------------------------------------------------

print("\nCOMPARACION:")
print("=" * 70)

for vehicle in vehicles:

    box = tuple(vehicle["box"])

    print(
        f"\nVehículo: {vehicle['label']} "
        f"{vehicle['confidence']:.2%}"
    )

    print(
        "Box:",
        box
    )

    found = False

    for space_id, polygon in spaces:

        occupied = overlap_is_significant(
            polygon,
            box
        )

        if occupied:

            found = True

            print(
                f"  >>> OCUPA ESPACIO {space_id}"
            )

    if not found:

        print(
            "  >>> NO COINCIDE CON NINGUN ESPACIO"
        )


print("\n")
print("=" * 70)
print("FIN DE LA PRUEBA")
print("=" * 70)