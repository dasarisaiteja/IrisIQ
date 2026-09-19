import os
import cv2

from utils.iris_segmentation import segment_iris
from utils.iris_normalization import normalize_iris

DATASET = "dataset/CASIA-Iris-Thousand"
OUTPUT = "processed_dataset"

os.makedirs(OUTPUT, exist_ok=True)

count = 0
failed = 0

for person in os.listdir(DATASET):

    person_path = os.path.join(DATASET, person)

    if not os.path.isdir(person_path):
        continue

    for eye in ["L", "R"]:

        eye_path = os.path.join(person_path, eye)

        if not os.path.exists(eye_path):
            continue

        save_folder = os.path.join(OUTPUT, person, eye)
        os.makedirs(save_folder, exist_ok=True)

        for img_name in os.listdir(eye_path):

            if not img_name.lower().endswith((".jpg", ".jpeg", ".png", ".bmp")):
                continue

            img_path = os.path.join(eye_path, img_name)

            img = cv2.imread(img_path)

            if img is None:
                failed += 1
                print(f"Image not loaded : {img_path}")
                continue

            try:

                # Iris Detection
                segmented, circle = segment_iris(img)

                if circle is None:
                    failed += 1
                    print(f"No iris detected : {img_path}")
                    continue

                # Iris Normalization
                normalized = normalize_iris(segmented, circle)

                if normalized is None:
                    failed += 1
                    print(f"Normalization failed : {img_path}")
                    continue

                if normalized.size == 0:
                    failed += 1
                    print(f"Empty image : {img_path}")
                    continue

                save_path = os.path.join(save_folder, img_name)

                success = cv2.imwrite(save_path, normalized)

                if success:
                    count += 1

                    if count % 100 == 0:
                        print(f"Processed : {count}")

                else:
                    failed += 1
                    print(f"Save failed : {img_path}")

            except Exception as e:

                failed += 1

                print(f"\nFailed : {img_path}")
                print("Reason :", str(e))

print("\n===================================")
print("Dataset Preprocessing Completed")
print("===================================")
print("Processed :", count)
print("Failed    :", failed)
print("===================================")