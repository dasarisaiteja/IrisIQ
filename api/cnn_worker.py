import os
import sys
import json

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

os.chdir(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)

os.environ["PYTHONUNBUFFERED"] = "1"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["TF_NUM_INTRAOP_THREADS"] = "1"
os.environ["TF_NUM_INTEROP_THREADS"] = "1"

import cv2

from utils.iris_segmentation import segment_iris
from utils.iris_normalization import normalize_iris
from utils.cnn_extractor import extract_cnn_features


if len(sys.argv) < 2:
    print("ERROR: employee code missing")
    sys.exit(2)

employee_code = sys.argv[1]


yolo_file = os.path.join(
    PROJECT_ROOT,
    "outputs",
    "enrollment",
    employee_code + "_yolo.json"
)


if not os.path.exists(yolo_file):

    print(
        "ERROR: YOLO result file not found:",
        yolo_file
    )

    sys.exit(3)


with open(
    yolo_file,
    "r"
) as f:

    yolo_results = json.load(f)


print("=" * 70)
print("CNN BATCH WORKER STARTED")
print("Employee :", employee_code)
print("YOLO Results :", len(yolo_results))
print("=" * 70)


all_embeddings = []


for index, item in enumerate(yolo_results):

    print()
    print("=" * 60)
    print(
        "CNN IMAGE",
        index + 1,
        "/",
        len(yolo_results)
    )
    print("=" * 60)

    image_path = item.get(
        "image"
    )

    crop_path = item.get(
        "crop_path"
    )

    if not crop_path:

        print(
            "Crop path missing"
        )

        continue


    # --------------------------------------------------------
    # READ CROP
    # --------------------------------------------------------

    image = cv2.imread(
        crop_path
    )

    if image is None:

        print(
            "Could not read crop:",
            crop_path
        )

        continue


    # --------------------------------------------------------
    # IRIS SEGMENTATION
    # --------------------------------------------------------

    try:

        print(
            "Running segmentation..."
        )

        iris_image, iris = segment_iris(
            image
        )

    except Exception as error:

        print(
            "SEGMENTATION ERROR :",
            error
        )

        continue


    if iris is None:

        print(
            "Iris not detected"
        )

        continue


    # --------------------------------------------------------
    # NORMALIZATION
    # --------------------------------------------------------

    try:

        print(
            "Running normalization..."
        )

        normalized = normalize_iris(
            image,
            iris
        )

    except Exception as error:

        print(
            "NORMALIZATION ERROR :",
            error
        )

        continue


    if normalized is None:

        print(
            "Normalization failed"
        )

        continue


    # --------------------------------------------------------
    # CNN
    # --------------------------------------------------------

    try:

        print(
            "Running CNN..."
        )

        embedding = extract_cnn_features(
            normalized
        )

    except Exception as error:

        print(
            "CNN ERROR :",
            error
        )

        continue


    if embedding is None:

        print(
            "Embedding failed"
        )

        continue


    all_embeddings.append(
        (
            embedding,
            image_path
        )
    )

    print(
        "Embedding Generated :",
        index + 1
    )


# ============================================================
# SAVE CNN RESULTS
# ============================================================

output_dir = os.path.join(
    PROJECT_ROOT,
    "outputs",
    "enrollment"
)

os.makedirs(
    output_dir,
    exist_ok=True
)


output_file = os.path.join(
    output_dir,
    employee_code + "_embeddings.json"
)


json_embeddings = []

for embedding, image_path in all_embeddings:

    json_embeddings.append(
        {
            "embedding": embedding,
            "image": image_path
        }
    )


with open(
    output_file,
    "w"
) as f:

    json.dump(
        json_embeddings,
        f
    )


print()
print("=" * 70)
print(
    "CNN BATCH COMPLETED"
)
print(
    "Embeddings :",
    len(all_embeddings)
)
print(
    "Output :",
    output_file
)
print("=" * 70)


if not all_embeddings:

    print(
        "ERROR: No embeddings generated"
    )

    sys.exit(4)


sys.exit(0)
