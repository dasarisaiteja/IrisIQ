import cv2
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Model

# Load trained CNN
base_model = tf.keras.models.load_model("models/iris_cnn.keras")

feature_model = tf.keras.Model(
    inputs=base_model.inputs,
    outputs=base_model.get_layer("embedding").output
)


def extract_cnn_features(image):

    if image is None:
        return None

    image = cv2.resize(
        image,
        (224,224)
    )

    image = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2RGB
    )

    image = image.astype(np.float32)

    image /= 255.0

    image = np.expand_dims(
        image,
        axis=0
    )

    embedding = feature_model.predict(
        image,
        verbose=0
    )

    embedding = embedding.flatten()

    embedding = embedding / np.linalg.norm(embedding)

    return embedding.tolist()