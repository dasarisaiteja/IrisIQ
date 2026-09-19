import cv2

from utils.iris_segmentation import segment_iris
from utils.iris_crop import crop_iris


img = cv2.imread("dataset/CASIA-Iris-Thousand/001/L/S5001L00.jpg")

result, circle = segment_iris(img)

iris = crop_iris(img, circle)

cv2.imshow("Original", img)
cv2.imshow("Segmented", result)
cv2.imshow("Iris Crop", iris)

cv2.waitKey(0)
cv2.destroyAllWindows()