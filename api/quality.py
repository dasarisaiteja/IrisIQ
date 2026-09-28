from fastapi import APIRouter, UploadFile, File, Form, Depends
from fastapi.responses import JSONResponse
import cv2
import numpy as np
import os
import shutil
from typing import Optional, Dict, Any

from utils.iris_quality_analyzer import analyze_iris_quality
from security.upload_validator import validate_uploaded_image
from security.auth import require_authenticated

router = APIRouter(prefix="/api/quality", tags=["Iris Quality"])

TEMP_FOLDER = "uploads"
os.makedirs(TEMP_FOLDER, exist_ok=True)


@router.post("/analyze")
async def analyze_quality(
    file: UploadFile = File(...),
    pupil_x: Optional[float] = Form(None),
    pupil_y: Optional[float] = Form(None),
    pupil_r: Optional[float] = Form(None),
    iris_x: Optional[float] = Form(None),
    iris_y: Optional[float] = Form(None),
    iris_r: Optional[float] = Form(None),
    confidence: Optional[float] = Form(None),
    current_user: Dict[str, Any] = Depends(require_authenticated)
):
    """
    Analyzes capture quality for an iris image/crop without performing identity prediction.
    """
    try:
        contents, _ = await validate_uploaded_image(file)
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            return JSONResponse(
                status_code=400,
                content={"status": False, "message": "Could not decode image"}
            )

        pupil = None
        if pupil_x is not None and pupil_y is not None and pupil_r is not None:
            pupil = (pupil_x, pupil_y, pupil_r)

        iris = None
        if iris_x is not None and iris_y is not None and iris_r is not None:
            iris = (iris_x, iris_y, iris_r)

        result = analyze_iris_quality(
            image=image,
            pupil=pupil,
            iris=iris,
            detection_confidence=confidence
        )

        return JSONResponse(content={"status": True, "quality": result})

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": False, "message": f"Quality analysis failed: {str(e)}"}
        )
