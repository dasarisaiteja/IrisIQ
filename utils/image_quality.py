import cv2


def is_blur(image, threshold=20):
    """
    Returns True if image is blurry.

    threshold:
        15-20  = Webcam (Recommended)
        25-30  = HD Camera
        100+   = Very Strict
    """

    if image is None:
        return True

    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY
    )

    variance = cv2.Laplacian(
        gray,
        cv2.CV_64F
    ).var()

    print("=" * 50)
    print("Blur Threshold :", threshold)
    print("Blur Score     :", round(variance, 2))
    print("=" * 50)

    if variance < threshold:
        print("Result : BLUR")
        return True

    print("Result : CLEAR")
    return False