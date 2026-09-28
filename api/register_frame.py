from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any

from utils.image_quality import is_blur
from security.path_validator import validate_identifier
from security.upload_validator import validate_uploaded_image
from security.auth import require_authenticated

import os
import shutil
import cv2

router = APIRouter()

UPLOAD_FOLDER = "uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@router.post("/register-frame")
async def register_frame(

    employee_code: str = Form(...),

    file: UploadFile = File(...),

    current_user: Dict[str, Any] = Depends(require_authenticated)

):

    # 1. Validate employee_code
    try:
        employee_code = validate_identifier(employee_code, "employee_code")
    except HTTPException as he:
        return JSONResponse(
            status_code=he.status_code,
            content={"saved": False, "message": he.detail, "employee_code": str(employee_code)}
        )

    # 2. Validate uploaded file
    try:
        image_bytes, safe_filename = await validate_uploaded_image(file)
    except HTTPException as he:
        return JSONResponse(
            status_code=he.status_code,
            content={"saved": False, "message": he.detail}
        )

    try:

        # ---------------- Employee Folder ----------------

        folder = os.path.abspath(os.path.join(
            UPLOAD_FOLDER,
            os.path.basename(employee_code)
        ))

        if not folder.startswith(os.path.abspath(UPLOAD_FOLDER)):
            return JSONResponse(
                status_code=403,
                content={"saved": False, "message": "Path traversal detected"}
            )

        os.makedirs(folder, exist_ok=True)

        # ---------------- Count Existing Images ----------------

        images = [
            f for f in os.listdir(folder)
            if f.lower().endswith(".jpg")
        ]

        count = len(images)

        # ---------------- Stop At 40 ----------------

        if count >= 40:

            return JSONResponse({

                "saved": True,

                "completed": True,

                "count": 40,

                "message": "40 Images Completed"

            })

        # ---------------- File Name ----------------

        filename = f"{count + 1:03d}.jpg"

        filepath = os.path.join(
            folder,
            filename
        )

        # ---------------- Save Image ----------------

        with open(filepath, "wb") as buffer:

            buffer.write(image_bytes)

        print("=" * 60)
        print("FRAME SAVED")
        print("Employee :", employee_code)
        print("File :", filename)
        print("=" * 60)

        # ---------------- Read Image ----------------

        image = cv2.imread(filepath)

        if image is None:

            os.remove(filepath)

            return JSONResponse({

                "saved": False,

                "message": "Invalid Image"

            })

        # ---------------- Blur Check ----------------

        #if is_blur(image):

            #os.remove(filepath)

            #print("Blur Image Rejected")

            #return JSONResponse({

                #"saved": False,

                #"message": "Blur Image"

            #})

        # ---------------- Success ----------------

        return JSONResponse({

            "saved": True,

            "completed": False,

            "count": count + 1,

            "file": filename

        })

    except Exception as ex:

        print(ex)

        return JSONResponse({

            "saved": False,

            "message": str(ex)

        }, status_code=500)