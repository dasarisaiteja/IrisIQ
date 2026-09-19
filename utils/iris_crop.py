import cv2
import numpy as np


def crop_iris(image, circle):

    if circle is None:
        return None

    x, y, r = circle

    mask = np.zeros(image.shape[:2], dtype=np.uint8)

    cv2.circle(mask, (x, y), r, 255, -1)

    iris = cv2.bitwise_and(image, image, mask=mask)

    x1 = max(x - r, 0)
    y1 = max(y - r, 0)

    x2 = min(x + r, image.shape[1])
    y2 = min(y + r, image.shape[0])

    iris = iris[y1:y2, x1:x2]

    iris = cv2.resize(iris, (224, 224))

    return iris