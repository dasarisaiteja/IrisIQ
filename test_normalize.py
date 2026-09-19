import cv2

from utils.iris_segmentation import segment_iris
from utils.iris_normalization import normalize_iris

img = cv2.imread(
    "dataset/CASIA-Iris-Thousand/001/L/S5001L00.jpg"
)

segmented, circle = segment_iris(img)

normalized = normalize_iris(img, circle)

cv2.imshow("Original", img)
cv2.imshow("Normalized Iris", normalized)

cv2.waitKey(0)
cv2.destroyAllWindows()