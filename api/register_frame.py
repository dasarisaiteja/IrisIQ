from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse

from utils.image_quality import is_blur

import os
import shutil
import cv2

router = APIRouter()

UPLOAD_FOLDER = "uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@router.post("/register-frame")
async def register_frame(

    employee_code: str = Form(...),

    file: UploadFile = File(...)

):

    try:

        # ---------------- Employee Folder ----------------

        folder = os.path.join(
            UPLOAD_FOLDER,
            employee_code
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

            shutil.copyfileobj(
                file.file,
                buffer
            )

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