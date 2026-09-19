import cv2

from utils.pupil_detection import detect_pupil

img = cv2.imread("dataset/CASIA-Iris-Thousand/001/L/S5001L00.jpg")

result, pupil = detect_pupil(img)

print(pupil)

cv2.imshow("Pupil Detection", result)

cv2.waitKey(0)
cv2.destroyAllWindows()