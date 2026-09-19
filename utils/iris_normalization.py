import cv2
import numpy as np
import os


def normalize_iris(image, circle, size=(512, 64)):

    if circle is None:
        return None

    x, y, r = circle

    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    normalized = cv2.warpPolar(
        gray,
        size,
        (float(x), float(y)),
        float(r),
        cv2.WARP_POLAR_LINEAR + cv2.WARP_FILL_OUTLIERS
    )

    normalized = cv2.rotate(
        normalized,
        cv2.ROTATE_90_CLOCKWISE
    )

    normalized = cv2.equalizeHist(normalized)

    os.makedirs("outputs", exist_ok=True)

    cv2.imwrite(
        "outputs/normalized_iris.jpg",
        normalized
    )

    return normalized