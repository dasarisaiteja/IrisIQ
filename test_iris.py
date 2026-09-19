import cv2
from utils.iris_segmentation import segment_iris

img = cv2.imread("dataset/CASIA-Iris-Thousand/001/L/S5001L00.jpg")

result, circle = segment_iris(img)

print(circle)

cv2.imshow("Iris Detection", result)
cv2.waitKey(0)
cv2.destroyAllWindows()