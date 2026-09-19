import os
import tensorflow as tf
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.layers import Dense
from tensorflow.keras.layers import Dropout
from tensorflow.keras.layers import BatchNormalization
from tensorflow.keras.layers import GlobalAveragePooling2D
from tensorflow.keras.models import Model
from tensorflow.keras.models import load_model
from tensorflow.keras.callbacks import EarlyStopping
from tensorflow.keras.callbacks import ReduceLROnPlateau
from tensorflow.keras.callbacks import ModelCheckpoint

print("########################################")
print("        IRIS CNN TRAINING")
print("########################################")

# =====================================================
# CONFIG
# =====================================================

DATASET = "training_dataset"

MODEL_PATH = "models/iris_cnn.keras"

IMG_SIZE = (224,224)

BATCH_SIZE = 16

INITIAL_EPOCH = 25

EPOCHS = 50

os.makedirs("models",exist_ok=True)

# =====================================================
# DATASET
# =====================================================

train_datagen = ImageDataGenerator(
    rescale=1./255,
    validation_split=0.20,
    rotation_range=8,
    zoom_range=0.20,
    width_shift_range=0.10,
    height_shift_range=0.10,
    brightness_range=[0.8,1.2],
    fill_mode="nearest"
)

train_data = train_datagen.flow_from_directory(
    DATASET,
    target_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    subset="training",
    class_mode="categorical",
    shuffle=True
)

val_data = train_datagen.flow_from_directory(
    DATASET,
    target_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    subset="validation",
    class_mode="categorical",
    shuffle=False
)

# =====================================================
# MODEL
# =====================================================

if os.path.exists(MODEL_PATH):

    print("\nLoading Existing Model...")

    model = load_model(MODEL_PATH)

else:

    print("\nCreating New Model...")

    base_model = MobileNetV2(
        weights="imagenet",
        include_top=False,
        input_shape=(224,224,3)
    )

    base_model.trainable = False

    x = base_model.output
    x = GlobalAveragePooling2D()(x)
    x = BatchNormalization()(x)
    x = Dense(512,activation="relu")(x)
    x = Dropout(0.4)(x)
    embedding = Dense(
        256,
        activation="relu",
        name="embedding"
    )(x)

    output = Dense(
        train_data.num_classes,
        activation="softmax",
        name="classifier"
    )(embedding)

    model = Model(
        inputs=base_model.input,
        outputs=output
    )

# =====================================================
# FINE TUNING
# =====================================================

print("\nFine Tuning Last Layers...")

for layer in model.layers[:-30]:
    layer.trainable=False

for layer in model.layers[-30:]:
    layer.trainable=True

# =====================================================
# COMPILE
# =====================================================

model.compile(

    optimizer=tf.keras.optimizers.Adam(
        learning_rate=1e-5
    ),

    loss="categorical_crossentropy",

    metrics=["accuracy"]

)

model.summary()

# =====================================================
# CALLBACKS
# =====================================================

callbacks=[

    EarlyStopping(
        monitor="val_loss",
        patience=5,
        restore_best_weights=True
    ),

    ReduceLROnPlateau(
        monitor="val_loss",
        factor=0.5,
        patience=2,
        verbose=1
    ),

    ModelCheckpoint(
        MODEL_PATH,
        monitor="val_accuracy",
        save_best_only=True,
        verbose=1
    )

]

# =====================================================
# TRAIN
# =====================================================

print(f"\nTraining Epoch {INITIAL_EPOCH+1} to {EPOCHS}")

history=model.fit(

    train_data,

    validation_data=val_data,

    epochs=EPOCHS,

    initial_epoch=INITIAL_EPOCH,

    callbacks=callbacks

)

# =====================================================
# SAVE
# =====================================================

model.save(MODEL_PATH)

print("\n================================")
print("MODEL SAVED")
print(MODEL_PATH)
print("================================") 