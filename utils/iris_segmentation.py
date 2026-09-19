import cv2
import numpy as np
import os


def segment_iris(image):

    if image is None:
        return None, None

    # ---------------- Convert to Gray ----------------

    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY
    )

    # ---------------- Improve Contrast ----------------

    gray = cv2.equalizeHist(gray)

    # ---------------- Blur ----------------

    gray = cv2.GaussianBlur(
        gray,
        (9, 9),
        2
    )

    h, w = gray.shape

    # ---------------- Radius ----------------

    min_radius = int(min(h, w) * 0.12)
    max_radius = int(min(h, w) * 0.48)

    print("===================================")
    print("IRIS SEGMENTATION")
    print("Image Size :", w, "x", h)
    print("Radius :", min_radius, "-", max_radius)
    print("===================================")

    # ---------------- Hough Circle ----------------

    circles = cv2.HoughCircles(

        gray,

        cv2.HOUGH_GRADIENT,

        dp=1.2,

        minDist=30,

        param1=60,

        param2=12,

        minRadius=min_radius,

        maxRadius=max_radius

    )

    output = image.copy()

    os.makedirs("outputs", exist_ok=True)

    # Save debug images
    cv2.imwrite(
        "outputs/debug_crop.jpg",
        image
    )

    cv2.imwrite(
        "outputs/debug_gray.jpg",
        gray
    )

    if circles is None:

        print("No Iris Found")

        return output, None

    circles = np.round(circles[0]).astype(int)

    print("Total Circles :", len(circles))

    image_center = np.array([w // 2, h // 2])

    best_circle = None
    best_score = float("inf")

    expected_radius = (min_radius + max_radius) / 2

    for i, c in enumerate(circles):

        x, y, r = c

        distance = np.linalg.norm(
            np.array([x, y]) - image_center
        )

        score = (distance * 2) + abs(r - expected_radius)

        print("--------------------------------")
        print("Circle :", i)
        print("Center :", x, y)
        print("Radius :", r)
        print("Distance :", distance)
        print("Score :", score)

        if score < best_score:

            best_score = score
            best_circle = c

    if best_circle is None:

        print("Best Circle Not Found")

        return output, None

    x, y, r = best_circle

    print("===================================")
    print("FINAL IRIS")
    print("Center :", x, y)
    print("Radius :", r)
    print("===================================")

    # Draw Iris

    cv2.circle(
        output,
        (x, y),
        r,
        (0, 255, 0),
        3
    )

    cv2.circle(
        output,
        (x, y),
        3,
        (0, 0, 255),
        -1
    )

    cv2.imwrite(
        "outputs/iris_segment.jpg",
        output
    )

    return output, (x, y, r)