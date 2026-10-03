from pathlib import Path

from PIL import Image
from ultralytics import YOLO


# ==========================================================
# RUTAS
# ==========================================================

# test_yolo.py está dentro de:
#
# artifacts/smartpark/
#
# El modelo está dentro de:
#
# artifacts/smartpark/data/models/yolo11n.pt

BASE_DIR = Path(__file__).resolve().parent

MODEL_PATH = (
    BASE_DIR
    / "data"
    / "models"
    / "yolo11n.pt"
)


# ==========================================================
# IMAGEN A PROBAR
# ==========================================================

# CAMBIA SOLAMENTE ESTA RUTA
# por la ubicación REAL de tu imagen.

IMAGE_PATH = Path(
    r"C:\Users\Administrador\Pictures\Screenshots\buu.png"
)


# ==========================================================
# ENCABEZADO
# ==========================================================

print("====================================") 
print(" SMARTPARK - PRUEBA DIRECTA YOLO")
print("====================================")
print()


# ==========================================================
# COMPROBAR MODELO
# ==========================================================

print("Ruta del modelo:")

print(MODEL_PATH)

print()

if not MODEL_PATH.exists():

    print("ERROR:")
    print("No se encontró el modelo YOLO.")
    print()

    print(
        "Verifica que exista:"
    )

    print(
        MODEL_PATH
    )

    raise SystemExit


print("Cargando modelo...")

model = YOLO(
    str(MODEL_PATH)
)

print("Modelo cargado correctamente.")
print()


# ==========================================================
# COMPROBAR IMAGEN
# ==========================================================

print("Ruta de imagen:")

print(IMAGE_PATH)

print()

if not IMAGE_PATH.exists():

    print("ERROR:")
    print("No se encontró la imagen.")

    print()
    print(
        "Cambia IMAGE_PATH por la ruta correcta."
    )

    raise SystemExit


print("Cargando imagen...")

image = Image.open(
    IMAGE_PATH
)

print(
    f"Tamaño de imagen: "
    f"{image.width}x{image.height}"
)

print()


# ==========================================================
# EJECUTAR YOLO
# ==========================================================

print("Ejecutando YOLO...")
print()

results = model.predict(
    source=str(IMAGE_PATH),

    # Confianza extremadamente baja
    # para poder observar detecciones débiles.
    conf=0.01,

    imgsz=1280,

    device="cpu",

    verbose=False,
)


# ==========================================================
# RESULTADOS
# ==========================================================

total = 0

vehicle_total = 0


VEHICLES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}


for result in results:

    if result.boxes is None:
        continue

    for box in result.boxes:

        cls = int(
            box.cls[0].item()
        )

        confidence = float(
            box.conf[0].item()
        )

        x1, y1, x2, y2 = (
            box.xyxy[0].tolist()
        )

        name = model.names.get(
            cls,
            str(cls),
        )

        print(
            f"Detectado: {name} | "
            f"confianza: {confidence:.2%} | "
            f"box: "
            f"({int(x1)}, {int(y1)}, "
            f"{int(x2)}, {int(y2)})"
        )

        total += 1

        if cls in VEHICLES:

            vehicle_total += 1


# ==========================================================
# RESUMEN
# ==========================================================

print()

print("====================================")
print(
    f"TOTAL DETECCIONES: {total}"
)
print(
    f"VEHÍCULOS: {vehicle_total}"
)
print("====================================")