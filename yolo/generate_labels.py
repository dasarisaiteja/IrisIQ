import os
import cv2
import shutil

from utils.iris_segmentation import segment_iris

SOURCE = "dataset/CASIA-Iris-Thousand"

TRAIN_IMAGES = "yolo/dataset/images/train"
TRAIN_LABELS = "yolo/dataset/labels/train"

os.makedirs(TRAIN_IMAGES, exist_ok=True)
os.makedirs(TRAIN_LABELS, exist_ok=True)

count = 0
failed = 0

for person in os.listdir(SOURCE):

    person_path = os.path.join(SOURCE, person)

    if not os.path.isdir(person_path):
        continue

    for eye in ["L", "R"]:

        eye_path = os.path.join(person_path, eye)

        if not os.path.exists(eye_path):
            continue

        for file in os.listdir(eye_path):

            if not file.lower().endswith(".jpg"):
                continue

            img_path = os.path.join(eye_path, file)

            img = cv2.imread(img_path)

            if img is None:
                failed += 1
                continue

            result, circle = segment_iris(img)

            if circle is None:
                failed += 1
                continue

            x, y, r = circle

            h, w = img.shape[:2]

            xc = x / w
            yc = y / h
            bw = (r * 2) / w
            bh = (r * 2) / h

            image_name = f"{person}_{eye}_{file}"

            shutil.copy(img_path, os.path.join(TRAIN_IMAGES, image_name))

            label_path = os.path.join(
                TRAIN_LABELS,
                image_name.replace(".jpg", ".txt")
            )

            with open(label_path, "w") as f:
                f.write(f"0 {xc} {yc} {bw} {bh}")

            count += 1

            if count % 100 == 0:
                print("Processed:", count)

print()
print("Done")
print("Generated:", count)
print("Failed:", failed)