import os
import sys
import json
import cv2
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["TF_NUM_INTRAOP_THREADS"] = "1"
os.environ["TF_NUM_INTEROP_THREADS"] = "1"

from utils.pupil_detection import detect_pupil
from utils.iris_segmentation import segment_iris
from utils.iris_normalization import normalize_iris
from utils.feature_extractor import extract_features
from utils.lbp_extractor import calculate_lbp
from utils.gabor_extractor import apply_gabor
from utils.glcm_extractor import extract_glcm
from utils.entropy_extractor import calculate_entropy
from utils.color_analysis import analyze_color
from utils.cnn_extractor import extract_cnn_features


def json_converter(obj):
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return str(obj)


if len(sys.argv) < 2:
    print("ERROR: crop path missing")
    sys.exit(2)

crop_path = sys.argv[1]

try:
    print("====================================")
    print("VISION WORKER STARTED")
    print("Crop :", crop_path)
    print("====================================")

    image = cv2.imread(crop_path)

    if image is None:
        print("ERROR: Unable to read crop")
        sys.exit(3)

    print("Running pupil detection...")
    pupil_img, pupil = detect_pupil(image)

    print("Running iris segmentation...")
    iris_img, iris = segment_iris(image)

    if iris is None:
        print("ERROR: Iris not detected")
        sys.exit(4)

    print("Iris :", iris)

    print("Running normalization...")
    normalized = normalize_iris(image, iris)

    if normalized is None:
        print("ERROR: Normalization failed")
        sys.exit(5)

    os.makedirs("outputs", exist_ok=True)

    normalized_path = "outputs/normalized_iris.jpg"
    cv2.imwrite(normalized_path, normalized)

    print("Running feature extraction...")
    features = extract_features(pupil, iris, image)

    if features is None:
        print("ERROR: Feature extraction failed")
        sys.exit(6)

    print("Running LBP...")
    lbp = calculate_lbp(normalized)
    lbp_path = "outputs/lbp.jpg"
    cv2.imwrite(lbp_path, lbp)

    print("Running Gabor...")
    gabor = apply_gabor(normalized)
    gabor_path = "outputs/gabor.jpg"
    cv2.imwrite(gabor_path, gabor)

    print("Running GLCM...")
    glcm_features = extract_glcm(normalized)

    print("Running entropy...")
    entropy = calculate_entropy(normalized)

    print("Running color analysis...")
    color_analysis = {"eye_color": "Unknown"}

    temp = analyze_color(normalized)

    if temp is not None:
        color_analysis = temp

    print("Running CNN...")
    cnn_embedding = extract_cnn_features(normalized)

    if isinstance(cnn_embedding, np.ndarray):
        cnn_embedding = cnn_embedding.tolist()

    pupil_path = "outputs/pupil.jpg"
    segment_path = "outputs/iris_segment.jpg"

    if pupil_img is not None:
        cv2.imwrite(pupil_path, pupil_img)

    if iris_img is not None:
        cv2.imwrite(segment_path, iris_img)

    result = {
        "pupil": pupil,
        "iris": iris,
        "features": features,
        "glcm": glcm_features,
        "entropy": entropy,
        "color_analysis": color_analysis,
        "cnn_embedding": cnn_embedding,
        "images": {
            "pupil": pupil_path,
            "segmentation": segment_path,
            "normalized": normalized_path,
            "lbp": lbp_path,
            "gabor": gabor_path
        }
    }

    safe_result = json.loads(
        json.dumps(result, default=json_converter)
    )

    print("RESULT_JSON:" + json.dumps(safe_result))
    print("VISION WORKER COMPLETED")

    sys.exit(0)

except Exception as error:
    print("VISION WORKER ERROR:", str(error))
    sys.exit(10)
