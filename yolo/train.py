from ultralytics import YOLO

model = YOLO("yolo11n.pt")

model.train(
    data="yolo/data.yaml",
    epochs=50,
    imgsz=640,
    batch=8,
    patience=20,
    workers=0,
    name="iris_detector-3"
)