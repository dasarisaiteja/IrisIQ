import os
import shutil

SOURCE = "processed_dataset"
DESTINATION = "training_dataset"

os.makedirs(DESTINATION, exist_ok=True)

total_images = 0
total_persons = 0

for person in os.listdir(SOURCE):

    person_path = os.path.join(SOURCE, person)

    if not os.path.isdir(person_path):
        continue

    destination_person = os.path.join(DESTINATION, person)
    os.makedirs(destination_person, exist_ok=True)

    for eye in ["L", "R"]:

        eye_path = os.path.join(person_path, eye)

        if not os.path.exists(eye_path):
            continue

        for image in os.listdir(eye_path):

            source_image = os.path.join(eye_path, image)
            destination_image = os.path.join(destination_person, image)

            shutil.copy2(source_image, destination_image)

            total_images += 1

    total_persons += 1

print("\n==============================")
print("Dataset Prepared Successfully")
print("==============================")
print("Persons :", total_persons)
print("Images  :", total_images)
print("Saved To:", DESTINATION)