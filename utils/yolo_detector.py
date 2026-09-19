import os
import torch
from ultralytics import YOLO
import cv2

print("====================================")
print("Loaded yolo_detector.py")
print("====================================")

# ===========================
# LOAD MODEL
# ===========================

MODEL_PATH = "runs/detect/iris_detector-3-5/weights/best.pt"

print("Model Path :", MODEL_PATH)
print("Model Exists :", os.path.exists(MODEL_PATH))

# IMPORTANT:
# Do not load YOLO model globally.
# Model will be loaded inside detect_and_crop()
model = None

print("====================================")

os.makedirs("outputs/crops", exist_ok=True)


# ===========================
# DETECT & CROP IRIS
# ===========================

def detect_and_crop(image_path):

    global model

    print("====================================")
    print("Running detect_and_crop()")
    print("Image :", image_path)
    print("====================================")

    # ---------------- READ IMAGE ----------------

    image = cv2.imread(image_path)

    if image is None:
        print("Image not found :", image_path)
        return None

    print("Image Shape :", image.shape)

    h, w = image.shape[:2]

    # ---------------- LOAD YOLO MODEL ----------------

    if model is None:

        print("Loading YOLO model inside detect_and_crop()...")

        try:

            model = YOLO(MODEL_PATH)

            print("YOLO model loaded successfully")
            print("Model Classes :", model.names)

        except Exception as e:

            print("YOLO Model Load Error :", str(e))
            return None

    # ---------------- YOLO Prediction ----------------

    print("Starting YOLO prediction...")

    try:

        with torch.inference_mode():
            results = model.predict(
                source=image.copy(),
                imgsz=640,
                conf=0.05,
                iou=0.45,
                verbose=False,
                save=False,
                device="cpu",
                workers=0,
                compile=False,
                half=False,
                augment=False
            )

    except Exception as e:

        print("YOLO Prediction Error :", str(e))
        return None

    print("YOLO prediction completed")

    # ---------------- RESULTS ----------------

    if results is None:
        print("Results is None")
        return None

    print("Prediction Results :", len(results))

    if len(results) == 0:
        print("No prediction result")
        return None

    result = results[0]

    if result is None:
        print("Result is None")
        return None

    boxes = result.boxes

    if boxes is None:
        print("Boxes is None")
        return None

    print("Boxes Found :", len(boxes))

    if len(boxes) == 0:
        print("No iris detected")
        return None

    # ---------------- DETECTIONS ----------------

    print("========== DETECTIONS ==========")

    for i in range(len(boxes)):

        try:

            confidence = float(boxes.conf[i].item())

            class_id = int(boxes.cls[i].item())

            xyxy = (
                boxes.xyxy[i]
                .detach()
                .cpu()
                .numpy()
                .tolist()
            )

            print("------------------------")
            print("Detection :", i)
            print("Confidence :", confidence)
            print("Class :", class_id)
            print("XYXY :", xyxy)

        except Exception as e:

            print("Detection read error :", e)

    print("===============================")

    # ---------------- BEST DETECTION ----------------

    try:

        confidence_values = (
            boxes.conf
            .detach()
            .cpu()
            .numpy()
        )

        best_index = int(
            confidence_values.argmax()
        )

        best_box = (
            boxes.xyxy[best_index]
            .detach()
            .cpu()
            .numpy()
        )

        x1, y1, x2, y2 = [
            int(v) for v in best_box
        ]

        confidence = float(
            confidence_values[best_index]
        )

    except Exception as e:

        print("Best detection error :", e)
        return None

    print("Best Confidence :", confidence)

    # ---------------- ADD MARGIN ----------------

    margin = 25

    x1 = max(0, x1 - margin)
    y1 = max(0, y1 - margin)

    x2 = min(w, x2 + margin)
    y2 = min(h, y2 + margin)

    print(
        "Final BBox :",
        [x1, y1, x2, y2]
    )

    # ---------------- CROP ----------------

    crop = image[y1:y2, x1:x2]

    if crop is None or crop.size == 0:

        print("Invalid Crop")
        return None

    print("Crop Shape :", crop.shape)

    # ---------------- SAVE CROP ----------------

    filename = os.path.basename(image_path)

    crop_path = os.path.join(
        "outputs",
        "crops",
        filename
    )

    success = cv2.imwrite(
        crop_path,
        crop
    )

    if not success:

        print(
            "Failed to save crop :",
            crop_path
        )

        return None

    print(
        "Crop Saved :",
        crop_path
    )

    # ---------------- FINAL DATA ----------------

    data = {
        "bbox": [
            x1,
            y1,
            x2,
            y2
        ],
        "confidence": round(
            confidence,
            4
        ),
        "crop_path": crop_path
    }

    print("====================================")
    print("Detection Success")
    print(data)
    print("====================================")

    return data