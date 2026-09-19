import cv2
import numpy as np


def detect_pupil(image):

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)

    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.0,
        minDist=30,
        param1=60,
        param2=12,
        minRadius=10,
        maxRadius=80
    )

    output = image.copy()

    if circles is not None:

        circles = np.uint16(np.around(circles))

        x, y, r = circles[0][0]

        x = int(x)
        y = int(y)
        r = int(r)

        cv2.circle(output, (x, y), r, (255,0,0), 2)
        cv2.circle(output, (x,y),2,(0,255,255),3)

        return output, (x, y, r)

    # -----------------------
    # Fallback
    # -----------------------

    h, w = gray.shape

    x = w // 2
    y = h // 2
    r = min(w, h) // 6

    cv2.circle(output, (x, y), r, (255,0,0),2)

    return output, (x, y, r)