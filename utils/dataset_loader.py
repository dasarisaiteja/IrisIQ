import os
import cv2

DATASET_PATH = "dataset/CASIA-Iris-Thousand"

count = 0

for root, dirs, files in os.walk(DATASET_PATH):
    for file in files:
        if file.lower().endswith((".jpg", ".jpeg", ".bmp", ".png")):
            img = cv2.imread(os.path.join(root, file))
            if img is not None:
                count += 1

print("Total Images:", count)