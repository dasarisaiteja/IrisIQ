import math
import cv2
import numpy as np


def extract_features(pupil, iris, image):

    if pupil is None or iris is None:
        return None

    px, py, pr = pupil
    ix, iy, ir = iris

    # Radius Ratio
    ratio = pr / ir

    # Center Distance
    center_distance = math.sqrt(
        (px - ix) ** 2 +
        (py - iy) ** 2
    )

    # Area
    pupil_area = math.pi * (pr ** 2)
    iris_area = math.pi * (ir ** 2)

    # Iris Ring Thickness
    iris_thickness = ir - pr

    # Gray Image
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Mean Intensity
    mean_intensity = np.mean(gray)

    # Standard Deviation
    std_intensity = np.std(gray)

    features = {
        "pupil_radius": pr,
        "iris_radius": ir,

        "pupil_area": round(pupil_area, 2),
        "iris_area": round(iris_area, 2),

        "iris_thickness": round(iris_thickness, 2),

        "pupil_iris_ratio": round(ratio, 4),

        "center_distance": round(center_distance, 2),

        "mean_intensity": round(float(mean_intensity), 2),

        "std_intensity": round(float(std_intensity), 2)
    }

    return features