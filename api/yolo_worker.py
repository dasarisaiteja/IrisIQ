import os
import sys
import json
import cv2
import tempfile

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

sys.path.insert(0, PROJECT_ROOT)

# MUST be before torch / ultralytics import
os.environ["TORCHDYNAMO_DISABLE"] = "1"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"

from utils.yolo_detector import detect_and_crop


if len(sys.argv) < 2:
    print("ERROR: image path missing")
    sys.exit(2)


image_path = sys.argv[1]

print("====================================")
print("YOLO SINGLE IMAGE WORKER STARTED")
print("Image :", image_path)
print("====================================")


if not os.path.exists(image_path):
    print("ERROR: Image does not exist")
    sys.exit(2)


def run_detection(path):
    try:
        print("Trying image :", path)

        result = detect_and_crop(path)

        if result is not None:
            print("YOLO DETECTION SUCCESS")
            print("YOLO RESULT:", result)
            return result

        print("No iris detected for :", path)

    except Exception as error:
        print("YOLO ERROR :", str(error))

    return None


# ============================================================
# 1. ORIGINAL IMAGE
# ============================================================

result = run_detection(image_path)

if result is not None:
    print("RESULT_JSON:" + json.dumps(result))
    print("YOLO SINGLE IMAGE WORKER COMPLETED")
    sys.exit(0)


# ============================================================
# 2. ROTATE 90 CLOCKWISE
# ============================================================

print("====================================")
print("TRYING ROTATION 90 CLOCKWISE")
print("====================================")

image = cv2.imread(image_path)

if image is None:
    print("ERROR: Could not read image")
    sys.exit(3)


temp_files = []


def save_temp(img, name):
    path = os.path.join(
        tempfile.gettempdir(),
        "iris_" + name + ".jpg"
    )

    cv2.imwrite(
        path,
        img,
        [cv2.IMWRITE_JPEG_QUALITY, 95]
    )

    temp_files.append(path)

    return path


rotated_90 = cv2.rotate(
    image,
    cv2.ROTATE_90_CLOCKWISE
)

rotated_path = save_temp(
    rotated_90,
    "rot90"
)

result = run_detection(rotated_path)

if result is not None:
    # Copy generated crop back to normal output name
    print("ROTATED IMAGE DETECTION SUCCESS")
    print("RESULT_JSON:" + json.dumps(result))

    for path in temp_files:
        try:
            os.remove(path)
        except Exception:
            pass

    sys.exit(0)


# ============================================================
# 3. ROTATE 90 COUNTER CLOCKWISE
# ============================================================

print("====================================")
print("TRYING ROTATION 90 COUNTER CLOCKWISE")
print("====================================")

rotated_270 = cv2.rotate(
    image,
    cv2.ROTATE_90_COUNTERCLOCKWISE
)

rotated_270_path = save_temp(
    rotated_270,
    "rot270"
)

result = run_detection(rotated_270_path)

if result is not None:
    print("ROTATED 270 IMAGE DETECTION SUCCESS")
    print("RESULT_JSON:" + json.dumps(result))

    for path in temp_files:
        try:
            os.remove(path)
        except Exception:
            pass

    sys.exit(0)


# ============================================================
# 4. RESIZE IMAGE
# ============================================================

print("====================================")
print("TRYING RESIZED IMAGE")
print("====================================")

height, width = image.shape[:2]

max_dimension = 1280

if max(height, width) > max_dimension:

    scale = max_dimension / max(height, width)

    new_width = int(width * scale)
    new_height = int(height * scale)

    resized = cv2.resize(
        image,
        (new_width, new_height),
        interpolation=cv2.INTER_AREA
    )

else:
    resized = image


resized_path = save_temp(
    resized,
    "resized"
)

result = run_detection(resized_path)

if result is not None:
    print("RESIZED IMAGE DETECTION SUCCESS")
    print("RESULT_JSON:" + json.dumps(result))

    for path in temp_files:
        try:
            os.remove(path)
        except Exception:
            pass

    sys.exit(0)


# ============================================================
# FAILED
# ============================================================

print("====================================")
print("YOLO FAILED ALL IMAGE VARIANTS")
print("====================================")

for path in temp_files:
    try:
        os.remove(path)
    except Exception:
        pass

print("RESULT_JSON:null")

sys.exit(1)
