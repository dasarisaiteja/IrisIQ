import os
import sys
import json
import cv2
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

os.environ["TORCHDYNAMO_DISABLE"] = "1"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"

from utils.yolo_detector import detect_and_crop


def detect_one(image_path):
    temp_files = []

    try:
        result = detect_and_crop(image_path)
        if result is not None:
            return result

        image = cv2.imread(image_path)
        if image is None:
            return None

        def save_temp(img, name):
            path = os.path.join(
                tempfile.gettempdir(),
                "iris_batch_" + name + "_" + str(os.getpid()) + ".jpg"
            )
            cv2.imwrite(path, img, [cv2.IMWRITE_JPEG_QUALITY, 95])
            temp_files.append(path)
            return path

        rotated_90 = cv2.rotate(
            image,
            cv2.ROTATE_90_CLOCKWISE
        )

        path = save_temp(rotated_90, "rot90")
        result = detect_and_crop(path)

        if result is not None:
            return result

        rotated_270 = cv2.rotate(
            image,
            cv2.ROTATE_90_COUNTERCLOCKWISE
        )

        path = save_temp(rotated_270, "rot270")
        result = detect_and_crop(path)

        if result is not None:
            return result

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

        path = save_temp(resized, "resized")
        result = detect_and_crop(path)

        return result

    except Exception as error:
        print("YOLO ERROR:", str(error))
        return None

    finally:
        for path in temp_files:
            try:
                os.remove(path)
            except Exception:
                pass


if len(sys.argv) < 2:
    print("ERROR: input JSON missing")
    sys.exit(2)

input_file = sys.argv[1]

if not os.path.exists(input_file):
    print("ERROR: input file not found")
    sys.exit(3)

with open(input_file, "r") as f:
    images = json.load(f)

if not isinstance(images, list):
    print("ERROR: input must be a list")
    sys.exit(4)

print("=" * 70)
print("YOLO BATCH WORKER STARTED")
print("TOTAL IMAGES:", len(images))
print("=" * 70)

results = []

for index, image_path in enumerate(images, 1):

    print()
    print("PROCESSING YOLO:", index, "/", len(images))
    print("IMAGE:", image_path)

    if not os.path.exists(image_path):
        results.append({
            "image": image_path,
            "success": False,
            "result": None
        })
        continue

    result = detect_one(image_path)

    if result is not None:
        print("YOLO SUCCESS:", image_path)

        results.append({
            "image": image_path,
            "success": True,
            "result": result
        })
    else:
        print("YOLO FAILED:", image_path)

        results.append({
            "image": image_path,
            "success": False,
            "result": None
        })

output = {
    "total": len(images),
    "successful": sum(1 for x in results if x["success"]),
    "failed": sum(1 for x in results if not x["success"]),
    "results": results
}

print("RESULT_JSON:" + json.dumps(output))
print("=" * 70)
print("YOLO BATCH WORKER COMPLETED")
print("=" * 70)

sys.exit(0)
