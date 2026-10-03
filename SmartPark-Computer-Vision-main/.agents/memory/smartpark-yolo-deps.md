---
name: Ultralytics and OpenCV setup
description: Replit Python resolver and OpenCV wheel constraints for local YOLO inference.
---

In this workspace, verify the configured Python package source for `ultralytics` if resolution claims that no package versions exist. A PyTorch-only index is not a suitable source for the Ultralytics package itself; the normal Python package index should resolve it.

Ultralytics depends on regular `opencv-python`, which requires the system `libGL` runtime on Linux. Regular and headless OpenCV wheels both populate the `cv2` namespace; mixing or removing one can leave installed metadata with incomplete module files. Keep one OpenCV wheel, keep `libGL` available for the regular wheel, and reinstall the selected wheel if `cv2` is missing core attributes.

**Why:** The wrong index mapping blocked local inference setup, and uninstalling the duplicate headless wheel removed shared `cv2` files even though the regular wheel still appeared installed.

**How to apply:** When YOLO setup or `import cv2` fails, inspect the configured source and installed wheel files before changing the detection pipeline.