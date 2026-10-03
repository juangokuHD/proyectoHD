# SmartPark

SmartPark is a university-level computer-vision project for analyzing parking-lot images. It uses a local Ultralytics YOLO model to detect vehicles, compares their bounding boxes with camera-specific parking-space polygons, and reports available and occupied spaces.

The project includes a Streamlit application as requested and a Replit web preview that uses the same Python vision pipeline through the workspace API server.

## Problem statement

Manually checking parking availability from camera images is slow and inconsistent. SmartPark demonstrates how object detection and geometric overlap can turn a parking-lot image into a per-space occupancy estimate.

## Objectives

- Detect cars, motorcycles, buses, and trucks in a user-provided image.
- Let the user define camera-specific parking spaces as four-point polygons.
- Determine occupancy from polygon intersection, not just a vehicle center point.
- Visualize results and produce quantitative occupancy statistics.
- Store camera layouts locally as JSON and scale coordinates to other resolutions.

## Technologies

- Python 3.11
- Streamlit
- Ultralytics YOLO (pretrained `yolo11n.pt` by default)
- OpenCV, NumPy, Pillow
- JSON camera configuration
- React/Vite preview and an Express API bridge in Replit

Uploaded images are sent to this project's API service, where the Python worker runs the bundled YOLO11n model locally. No paid service or third-party AI API is used. In the Replit preview, inference runs in the Replit project environment, not in the visitor's browser or device.

## Installation

From this directory:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The Replit environment provides Python 3.11, the native OpenCV `libGL` runtime, and the listed libraries for the local preview. The bundled YOLO11n weights are stored in `data/models/`; no detections are fabricated if the model is unavailable. Ultralytics YOLO11 is distributed under AGPL-3.0; review that license before redistributing or deploying the project.

## Run

```bash
streamlit run app.py
```

For the Replit dashboard preview, start the `artifacts/api-server: API Server` and `artifacts/smartpark: web` workflows.

## How to use

1. Upload a PNG, JPG, or JPEG parking-lot image in the sidebar.
2. Select an existing camera view or choose **Configure a new camera**.
3. For a new camera, enter a name and click four corners of each parking-space polygon in clockwise order. Add each space and save the layout.
4. Select the saved camera view, set the confidence threshold, and choose **Analyze parking lot**.
5. Review the annotated image, space statuses, detection confidences, and occupancy statistics. Download the result as a PNG.

Camera layouts correspond to a specific camera/view. Reuse a layout only for the same view; for a new angle, create a separate camera configuration. Saved coordinates are relative to the reference image dimensions and are scaled independently on the x and y axes to match the uploaded image.

## How vehicle detection works

SmartPark loads Ultralytics YOLO once per Python process. It runs CPU inference with an image size of 1280 and the selected confidence threshold. Only COCO classes for cars, motorcycles, buses, and trucks are retained. Ultralytics letterboxes the input for inference while preserving its aspect ratio; returned boxes map back to the original image.

The default model is `yolo11n.pt`. Set `SMARTPARK_MODEL` to another compatible local or supported Ultralytics model name/path to change it.

## How occupancy is calculated

For each configured slot, SmartPark scales the four saved points to the current image size. For every detected vehicle box and parking polygon, OpenCV calculates their polygon intersection. A slot is marked **OCCUPIED** when the intersection covers at least 12% of the space and 20% of the smaller of the space or vehicle bounding-box areas. A slot is not classified from the vehicle center alone.

Occupancy percentage is `occupied spaces / total spaces × 100`. Levels are LOW below 50%, MEDIUM from 50% to under 80%, and HIGH at 80% or above. An image with zero detections still renders the configured parking-space overlays.

## Architecture

```text
Uploaded image
    └─ image validation and decode
        └─ local Ultralytics YOLO inference
            └─ vehicle bounding boxes + confidence
                └─ scaled parking-space polygons
                    └─ polygon intersection and occupancy classification
                        └─ annotated PNG + summary statistics
```

- `app.py` — Streamlit UI, upload, camera selection, mapping, analysis, and download.
- `vision/pipeline.py` — model cache, vehicle detection, overlap status, statistics, and image annotation.
- `vision/parking_spaces.py` — resolution scaling and polygon intersection threshold.
- `vision/camera_store.py` — atomic JSON persistence shared with the API.
- `vision/worker.py` — long-lived line-based worker used by the Replit API so the model stays loaded.
- `data/parking_spaces.json` — saved camera layouts.
- `components/parking_editor/index.html` — local Streamlit click-to-map component.
- `artifacts/api-server/src/routes/parking.ts` — camera CRUD and analysis API used by the web preview.

## Limitations

- Results depend on image quality, camera height/angle, lighting, occlusion, and the pretrained model's generalization.
- A layout is specific to one camera view; changing camera angle requires a new layout.
- The polygon overlap thresholds are fixed defaults and may need adjustment for unusual cameras or parking-space geometry.
- Detection runs on CPU in this project and can take longer on high-resolution images.
- The app does not reserve spaces, connect to live cameras, or provide a production parking enforcement guarantee.

## Possible future improvements

- Allow per-camera overlap thresholds and support layout editing.
- Add a calibration workflow and camera health checks.
- Compare multiple frames over time to reduce transient detection errors.
- Export CSV summaries and evaluate precision/recall on a labeled campus dataset.
- Add optional GPU inference where the deployment runtime supports it.