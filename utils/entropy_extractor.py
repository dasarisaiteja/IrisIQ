import cv2
import numpy as np


def calculate_entropy(image):

    if image is None:
        return 0

    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    hist = cv2.calcHist(
        [gray],
        [0],
        None,
        [256],
        [0, 256]
    )

    hist = hist / hist.sum()

    entropy = -np.sum(
        hist * np.log2(hist + 1e-10)
    )

    return round(float(entropy), 4)