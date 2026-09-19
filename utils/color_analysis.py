import cv2
import numpy as np


def analyze_color(image):

    if image is None:
        return None

    if len(image.shape) == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

    b, g, r = cv2.split(image)

    avg_r = float(np.mean(r))
    avg_g = float(np.mean(g))
    avg_b = float(np.mean(b))

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    h = float(np.mean(hsv[:, :, 0]))
    s = float(np.mean(hsv[:, :, 1]))
    v = float(np.mean(hsv[:, :, 2]))

    brightness = v
    saturation = s

    eye_color = "Unknown"

    if avg_r > avg_g and avg_r > avg_b:
        eye_color = "Brown"

    elif avg_b > avg_r and avg_b > avg_g:
        eye_color = "Blue"

    elif avg_g > avg_r and avg_g > avg_b:
        eye_color = "Green"

    return {
        "average_rgb": {
            "r": round(avg_r, 2),
            "g": round(avg_g, 2),
            "b": round(avg_b, 2)
        },

        "average_hsv": {
            "h": round(h, 2),
            "s": round(s, 2),
            "v": round(v, 2)
        },

        "brightness": round(brightness, 2),

        "saturation": round(saturation, 2),

        "eye_color": eye_color
    }