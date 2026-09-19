from utils.eye_detection import detect_eye
import cv2
import os

image_path = "dataset/CASIA-Iris-Thousand/001/L/S5001L00.jpg"
print("Exists:", os.path.exists(image_path))
print("Path:", image_path)

img = detect_eye(image_path)

if img is None:
    print("Image not loaded")
else:
    cv2.imshow("Eye", img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()