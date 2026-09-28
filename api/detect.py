from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any

import shutil
import os
import json
import subprocess
import sys
import traceback

from security.upload_validator import validate_uploaded_image
from security.auth import require_counselor_or_admin


router = APIRouter()


UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)

os.makedirs(
    OUTPUT_FOLDER,
    exist_ok=True
)


BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

PYTHON = os.path.join(
    BASE_DIR,
    "ai-env",
    "bin",
    "python3"
)

YOLO_WORKER = os.path.join(
    BASE_DIR,
    "api",
    "yolo_worker.py"
)

VISION_WORKER = os.path.join(
    BASE_DIR,
    "api",
    "vision_worker.py"
)


def run_worker(
    worker,
    argument,
    timeout=120
):

    command = [

        PYTHON,

        "-X",
        "faulthandler",

        "-u",

        worker,

        argument

    ]

    print("====================================")
    print("STARTING WORKER")
    print("Worker :", worker)
    print("Argument :", argument)
    print("====================================")


    try:

        process = subprocess.run(

            command,

            cwd=BASE_DIR,

            capture_output=True,

            text=True,

            timeout=timeout

        )


    except subprocess.TimeoutExpired:

        return {

            "success": False,

            "error": "Worker timeout"

        }


    print("Worker Return Code :", process.returncode)

    print("===== WORKER STDOUT =====")

    print(
        process.stdout
    )

    print("===== WORKER STDERR =====")

    print(
        process.stderr
    )


    result_json = None


    for line in process.stdout.splitlines():

        if line.startswith(
            "RESULT_JSON:"
        ):

            try:

                result_json = json.loads(
                    line[
                        len("RESULT_JSON:"):
                    ]
                )

            except Exception as error:

                return {

                    "success": False,

                    "error":
                        "Invalid worker JSON: "
                        + str(error)

                }


    if process.returncode != 0:

        return {

            "success": False,

            "error":
                "Worker failed",

            "return_code":
                process.returncode,

            "stdout":
                process.stdout,

            "stderr":
                process.stderr

        }


    if result_json is None:

        return {

            "success": False,

            "error":
                "Worker did not return RESULT_JSON",

            "stdout":
                process.stdout,

            "stderr":
                process.stderr

        }


    return {

        "success": True,

        "result": result_json

    }


@router.post("/detect")
async def detect(
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(require_counselor_or_admin)
):

    try:

        # ====================================================
        # VALIDATE UPLOADED FILE
        # ====================================================

        image_bytes, safe_filename = await validate_uploaded_image(file)

        file_path = os.path.join(
            UPLOAD_FOLDER,
            safe_filename
        )

        with open(
            file_path,
            "wb"
        ) as buffer:

            buffer.write(image_bytes)


        print("====================================")
        print("DETECT REQUEST")
        print("File :", file.filename)
        print("Path :", file_path)
        print("====================================")


        # ====================================================
        # YOLO WORKER
        # ====================================================

        yolo = run_worker(

            YOLO_WORKER,

            file_path,

            timeout=120

        )


        if not yolo["success"]:

            return JSONResponse(

                status_code=500,

                content={

                    "status": False,

                    "message":
                        "YOLO detection failed",

                    "error":
                        yolo.get("error"),

                    "return_code":
                        yolo.get("return_code")

                }

            )


        detection = yolo["result"]


        if detection is None:

            return {

                "status": False,

                "message":
                    "No Iris Detected"

            }


        crop_path = detection.get(
            "crop_path"
        )


        if not crop_path:

            return JSONResponse(

                status_code=500,

                content={

                    "status": False,

                    "message":
                        "YOLO did not return crop path"

                }

            )


        # ====================================================
        # VISION WORKER
        # ====================================================

        vision = run_worker(

            VISION_WORKER,

            crop_path,

            timeout=180

        )


        if not vision["success"]:

            return JSONResponse(

                status_code=500,

                content={

                    "status": False,

                    "message":
                        "Vision processing failed",

                    "error":
                        vision.get("error"),

                    "return_code":
                        vision.get("return_code")

                }

            )


        vision_result = vision["result"]


        # ====================================================
        # FINAL RESPONSE
        # ====================================================

        response = {

            "status": True,

            "file": file.filename,

            "detection": {

                "bbox":
                    detection.get("bbox"),

                "confidence":
                    detection.get("confidence")

            },

            "crop_path":
                crop_path,

            "pupil":
                vision_result.get("pupil"),

            "iris":
                vision_result.get("iris"),

            "features":
                vision_result.get("features"),

            "glcm":
                vision_result.get("glcm"),

            "entropy":
                vision_result.get("entropy"),

            "color_analysis":
                vision_result.get(
                    "color_analysis"
                ),

            "cnn_embedding":
                vision_result.get(
                    "cnn_embedding"
                ),

            "images": {

                "crop":
                    crop_path,

                "pupil":
                    vision_result[
                        "images"
                    ].get("pupil"),

                "segmentation":
                    vision_result[
                        "images"
                    ].get("segmentation"),

                "normalized":
                    vision_result[
                        "images"
                    ].get("normalized"),

                "lbp":
                    vision_result[
                        "images"
                    ].get("lbp"),

                "gabor":
                    vision_result[
                        "images"
                    ].get("gabor")

            }

        }


        # ====================================================
        # SAVE JSON
        # ====================================================

        with open(
            os.path.join(
                OUTPUT_FOLDER,
                "detect.json"
            ),
            "w"
        ) as f:

            json.dump(
                response,
                f,
                indent=4
            )


        print("====================================")
        print("DETECT SUCCESS")
        print("====================================")


        return JSONResponse(
            content=response
        )


    except Exception as ex:

        traceback.print_exc()

        return JSONResponse(

            status_code=500,

            content={

                "status": False,

                "message":
                    str(ex)

            }

        )
