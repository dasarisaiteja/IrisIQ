import os
import random
import shutil

random.seed(42)

TRAIN_IMAGES = "yolo/dataset/images/train"
TRAIN_LABELS = "yolo/dataset/labels/train"

VAL_IMAGES = "yolo/dataset/images/val"
VAL_LABELS = "yolo/dataset/labels/val"

os.makedirs(VAL_IMAGES, exist_ok=True)
os.makedirs(VAL_LABELS, exist_ok=True)

images = [f for f in os.listdir(TRAIN_IMAGES) if f.endswith(".jpg")]

random.shuffle(images)

val_count = int(len(images) * 0.2)

val_images = images[:val_count]

for img in val_images:

    shutil.move(
        os.path.join(TRAIN_IMAGES, img),
        os.path.join(VAL_IMAGES, img)
    )

    label = img.replace(".jpg", ".txt")

    shutil.move(
        os.path.join(TRAIN_LABELS, label),
        os.path.join(VAL_LABELS, label)
    )

print("=================================")
print("Dataset Split Completed")
print("Train :", len(images) - val_count)
print("Validation :", val_count)
print("=================================")