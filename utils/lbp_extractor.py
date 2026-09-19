import cv2
import numpy as np


def calculate_lbp(image):

    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    h, w = gray.shape

    lbp = np.zeros((h, w), dtype=np.uint8)

    for y in range(1, h - 1):
        for x in range(1, w - 1):

            center = gray[y, x]

            code = 0

            code |= (gray[y - 1, x - 1] >= center) << 7
            code |= (gray[y - 1, x] >= center) << 6
            code |= (gray[y - 1, x + 1] >= center) << 5
            code |= (gray[y, x + 1] >= center) << 4
            code |= (gray[y + 1, x + 1] >= center) << 3
            code |= (gray[y + 1, x] >= center) << 2
            code |= (gray[y + 1, x - 1] >= center) << 1
            code |= (gray[y, x - 1] >= center)

            lbp[y, x] = code

    return lbp