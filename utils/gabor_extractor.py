import cv2
import numpy as np
import os


def apply_gabor(image):

    if image is None:
        return None

    # Convert to Grayscale
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    # Improve contrast
    gray = cv2.equalizeHist(gray)

    # Create Gabor Kernel
    kernel = cv2.getGaborKernel(
        ksize=(31, 31),
        sigma=4.0,
        theta=np.pi / 4,
        lambd=10.0,
        gamma=0.5,
        psi=0,
        ktype=cv2.CV_32F
    )

    # Apply Gabor Filter (IMPORTANT: CV_32F)
    filtered = cv2.filter2D(
        gray,
        cv2.CV_32F,
        kernel
    )

    # Absolute values
    filtered = np.abs(filtered)

    # Normalize to 0-255
    filtered = cv2.normalize(
        filtered,
        None,
        0,
        255,
        cv2.NORM_MINMAX
    )

    # Convert to uint8
    filtered = filtered.astype(np.uint8)

    # Save image
    os.makedirs("outputs", exist_ok=True)

    cv2.imwrite(
        "outputs/gabor.jpg",
        filtered
    )

    return filtered