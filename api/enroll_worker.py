import os
import sys
import json
import subprocess
import tempfile


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

os.chdir(PROJECT_ROOT)

sys.path.insert(
    0,
    PROJECT_ROOT
)


# ============================================================
# ENVIRONMENT
# ============================================================

os.environ["PYTHONUNBUFFERED"] = "1"
os.environ["TORCHDYNAMO_DISABLE"] = "1"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"

os.environ["TF_NUM_INTRAOP_THREADS"] = "1"
os.environ["TF_NUM_INTEROP_THREADS"] = "1"


# ============================================================
# DATABASE
# ============================================================

from database import save_embeddings_bulk


# ============================================================
# EMPLOYEE CODE
# ============================================================

if len(sys.argv) < 2:
    print("ERROR: Employee code missing")
    sys.exit(2)

employee_code = sys.argv[1]

print("=" * 70)
print("AI BATCH ENROLLMENT WORKER STARTED")
print("Employee :", employee_code)
print("=" * 70)


# ============================================================
# PATHS
# ============================================================

UPLOAD_FOLDER = os.path.join(
    PROJECT_ROOT,
    "uploads",
    employee_code
)

OUTPUT_FOLDER = os.path.join(
    PROJECT_ROOT,
    "outputs",
    "enrollment"
)

os.makedirs(
    OUTPUT_FOLDER,
    exist_ok=True
)


# ============================================================
# CHECK EMPLOYEE FOLDER
# ============================================================

if not os.path.exists(UPLOAD_FOLDER):

    print(
        "ERROR: Employee upload folder not found:"
    )

    print(UPLOAD_FOLDER)

    sys.exit(3)


# ============================================================
# GET REGISTERED IMAGES
# ============================================================

images = []

for filename in os.listdir(UPLOAD_FOLDER):

    if filename.lower().endswith(
        (".jpg", ".jpeg", ".png")
    ):

        images.append(
            os.path.join(
                UPLOAD_FOLDER,
                filename
            )
        )

images.sort()


print()
print("=" * 70)
print(
    "REGISTERED IMAGES :",
    len(images)
)
print("=" * 70)


if not images:

    print(
        "ERROR: No registered images found"
    )

    sys.exit(4)


# ============================================================
# WORKER PATHS
# ============================================================

YOLO_BATCH_WORKER = os.path.join(
    PROJECT_ROOT,
    "api",
    "yolo_batch_worker.py"
)

VISION_BATCH_WORKER = os.path.join(
    PROJECT_ROOT,
    "api",
    "vision_batch_worker.py"
)

PYTHON = sys.executable


# ============================================================
# CHECK WORKERS
# ============================================================

if not os.path.exists(YOLO_BATCH_WORKER):

    print(
        "ERROR: YOLO batch worker not found:"
    )

    print(YOLO_BATCH_WORKER)

    sys.exit(5)


if not os.path.exists(VISION_BATCH_WORKER):

    print(
        "ERROR: Vision batch worker not found:"
    )

    print(VISION_BATCH_WORKER)

    sys.exit(6)


# ============================================================
# TEMP FILES
# ============================================================

temp_files = []


def create_json_file(data, prefix):

    fd, path = tempfile.mkstemp(
        prefix=prefix,
        suffix=".json",
        dir=OUTPUT_FOLDER
    )

    os.close(fd)

    with open(path, "w") as f:
        json.dump(data, f)

    temp_files.append(path)

    return path


# ============================================================
# ENVIRONMENT
# ============================================================

worker_env = os.environ.copy()

worker_env["PYTHONUNBUFFERED"] = "1"
worker_env["TORCHDYNAMO_DISABLE"] = "1"
worker_env["CUDA_VISIBLE_DEVICES"] = "-1"

worker_env["OMP_NUM_THREADS"] = "1"
worker_env["MKL_NUM_THREADS"] = "1"
worker_env["OPENBLAS_NUM_THREADS"] = "1"

worker_env["TF_NUM_INTRAOP_THREADS"] = "1"
worker_env["TF_NUM_INTEROP_THREADS"] = "1"


# ============================================================
# STEP 1
# YOLO BATCH
# ============================================================

print()
print("=" * 70)
print("STEP 1 : YOLO BATCH PROCESSING")
print("=" * 70)

yolo_input_file = create_json_file(
    images,
    employee_code + "_yolo_input_"
)

try:

    yolo_process = subprocess.run(
        [
            PYTHON,
            "-X",
            "faulthandler",
            "-u",
            YOLO_BATCH_WORKER,
            yolo_input_file
        ],

        cwd=PROJECT_ROOT,

        capture_output=True,

        text=True,

        timeout=900,

        env=worker_env
    )

except subprocess.TimeoutExpired:

    print("YOLO BATCH ERROR: Timeout")

    for path in temp_files:
        try:
            os.remove(path)
        except Exception:
            pass

    sys.exit(7)

except Exception as error:

    print(
        "YOLO BATCH PROCESS ERROR:",
        error
    )

    sys.exit(8)


print()
print(
    "YOLO Return Code :",
    yolo_process.returncode
)


if yolo_process.stdout:

    print("===== YOLO BATCH STDOUT =====")
    print(yolo_process.stdout)


if yolo_process.stderr:

    print("===== YOLO BATCH STDERR =====")
    print(yolo_process.stderr)


# ============================================================
# PARSE YOLO RESULT
# ============================================================

yolo_result = None

for line in (
    yolo_process.stdout or ""
).splitlines():

    line = line.strip()

    if line.startswith(
        "RESULT_JSON:"
    ):

        try:

            yolo_result = json.loads(
                line[
                    len("RESULT_JSON:"):
                ]
            )

        except Exception as error:

            print(
                "YOLO JSON ERROR:",
                error
            )


if (
    yolo_process.returncode != 0
    or yolo_result is None
):

    print()
    print("=" * 70)
    print("YOLO BATCH FAILED")
    print("=" * 70)

    sys.exit(9)


print()
print("=" * 70)
print("YOLO BATCH COMPLETED")
print(
    "Successful :",
    yolo_result.get("successful", 0)
)

print(
    "Failed :",
    yolo_result.get("failed", 0)
)
print("=" * 70)


# ============================================================
# PREPARE VISION INPUT
# ============================================================

vision_items = []

for item in yolo_result.get(
    "results",
    []
):

    if not item.get("success"):
        continue

    result = item.get(
        "result"
    )

    if not result:
        continue

    crop_path = result.get(
        "crop_path"
    )

    if not crop_path:
        continue

    if not os.path.isabs(
        crop_path
    ):

        crop_path = os.path.join(
            PROJECT_ROOT,
            crop_path
        )

    if not os.path.exists(
        crop_path
    ):

        print(
            "WARNING: Crop does not exist:",
            crop_path
        )

        continue

    vision_items.append(
        {
            "image": item.get(
                "image"
            ),
            "crop_path": crop_path
        }
    )


print()
print(
    "VISION INPUT IMAGES :",
    len(vision_items)
)


if not vision_items:

    print(
        "ERROR: No YOLO crops available for Vision"
    )

    sys.exit(10)


# ============================================================
# STEP 2
# VISION BATCH
# ============================================================

print()
print("=" * 70)
print("STEP 2 : VISION / CNN BATCH PROCESSING")
print("=" * 70)

vision_input_file = create_json_file(
    vision_items,
    employee_code + "_vision_input_"
)

try:

    vision_process = subprocess.run(
        [
            PYTHON,
            "-X",
            "faulthandler",
            "-u",
            VISION_BATCH_WORKER,
            vision_input_file
        ],

        cwd=PROJECT_ROOT,

        capture_output=True,

        text=True,

        timeout=1800,

        env=worker_env
    )

except subprocess.TimeoutExpired:

    print("VISION BATCH ERROR: Timeout")

    sys.exit(11)

except Exception as error:

    print(
        "VISION BATCH PROCESS ERROR:",
        error
    )

    sys.exit(12)


print()
print(
    "Vision Return Code :",
    vision_process.returncode
)


if vision_process.stdout:

    print("===== VISION BATCH STDOUT =====")
    print(vision_process.stdout)


if vision_process.stderr:

    print("===== VISION BATCH STDERR =====")
    print(vision_process.stderr)


# ============================================================
# PARSE VISION RESULT
# ============================================================

vision_result = None

for line in (
    vision_process.stdout or ""
).splitlines():

    line = line.strip()

    if line.startswith(
        "RESULT_JSON:"
    ):

        try:

            vision_result = json.loads(
                line[
                    len("RESULT_JSON:"):
                ]
            )

        except Exception as error:

            print(
                "VISION JSON ERROR:",
                error
            )


if (
    vision_process.returncode != 0
    or vision_result is None
):

    print()
    print("=" * 70)
    print("VISION BATCH FAILED")
    print("=" * 70)

    sys.exit(13)


# ============================================================
# COLLECT EMBEDDINGS
# ============================================================

all_embeddings = []
processed_images = []
failed_images = []


for item in vision_result.get(
    "results",
    []
):

    image_path = item.get(
        "image"
    )

    if not item.get("success"):

        if image_path:
            failed_images.append(
                image_path
            )

        continue

    result = item.get(
        "result"
    )

    if not result:

        if image_path:
            failed_images.append(
                image_path
            )

        continue

    embedding = result.get(
        "cnn_embedding"
    )

    if embedding is None:

        embedding = result.get(
            "embedding"
        )

    if not embedding:

        if image_path:
            failed_images.append(
                image_path
            )

        continue

    all_embeddings.append(
        (
            embedding,
            image_path
        )
    )

    if image_path:
        processed_images.append(
            image_path
        )


# ============================================================
# SUMMARY
# ============================================================

print()
print("=" * 70)
print("AI ENROLLMENT PROCESSING COMPLETED")
print("=" * 70)

print(
    "Total Images :",
    len(images)
)

print(
    "Successful Images :",
    len(processed_images)
)

print(
    "Failed Images :",
    len(failed_images)
)

print("=" * 70)


# ============================================================
# CHECK EMBEDDINGS
# ============================================================

if not all_embeddings:

    print(
        "ERROR: No embeddings generated"
    )

    sys.exit(14)


# ============================================================
# SAVE EMBEDDINGS JSON
# ============================================================

embedding_file = os.path.join(
    OUTPUT_FOLDER,
    employee_code +
    "_embeddings.json"
)

saved_data = []

for embedding, image_path in all_embeddings:

    saved_data.append(
        {
            "image": image_path,
            "embedding": embedding
        }
    )


try:

    with open(
        embedding_file,
        "w"
    ) as f:

        json.dump(
            saved_data,
            f
        )

    print()
    print(
        "Embeddings JSON Saved:"
    )

    print(
        embedding_file
    )

except Exception as error:

    print(
        "ERROR: Could not save embeddings JSON:"
    )

    print(error)

    sys.exit(15)


# ============================================================
# SAVE DATABASE EMBEDDINGS
# ============================================================

print()
print("=" * 70)
print("SAVING EMBEDDINGS TO DATABASE")
print("=" * 70)

try:

    save_embeddings_bulk(
        employee_code,
        all_embeddings
    )

    print(
        "ALL EMBEDDINGS SAVED SUCCESSFULLY"
    )

except Exception as error:

    print(
        "EMBEDDING DATABASE SAVE ERROR:"
    )

    print(error)

    sys.exit(16)


# ============================================================
# SAVE LAST EMBEDDING
# ============================================================

last_embedding = all_embeddings[-1][0]

last_embedding_file = os.path.join(
    OUTPUT_FOLDER,
    employee_code +
    "_last_embedding.json"
)

try:

    with open(
        last_embedding_file,
        "w"
    ) as f:

        json.dump(
            {
                "embedding": last_embedding
            },
            f
        )

    print()
    print(
        "Last embedding saved:"
    )

    print(
        last_embedding_file
    )

except Exception as error:

    print(
        "LAST EMBEDDING SAVE ERROR:"
    )

    print(error)

    sys.exit(17)


# ============================================================
# CLEAN TEMP FILES
# ============================================================

for path in temp_files:

    try:
        os.remove(path)
    except Exception:
        pass


# ============================================================
# FINAL RESULT
# ============================================================

print()
print("=" * 70)
print("AI BATCH ENROLLMENT WORKER COMPLETED SUCCESSFULLY")
print("=" * 70)

print(
    "Employee :",
    employee_code
)

print(
    "Total Images :",
    len(images)
)

print(
    "Successful Embeddings :",
    len(all_embeddings)
)

print(
    "Failed Images :",
    len(failed_images)
)

print(
    "Embedding File :",
    embedding_file
)

print("=" * 70)

sys.exit(0)
