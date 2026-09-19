from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse

import os
import json
import uuid
import asyncio
import traceback
import numpy as np

from database import (
    get_user,
    get_embeddings,
    get_employee_images
)

from utils.similarity import cosine_similarity


router = APIRouter()


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

UPLOAD_FOLDER = os.path.join(
    BASE_DIR,
    "uploads"
)

OUTPUT_FOLDER = os.path.join(
    BASE_DIR,
    "outputs"
)

REPORTS_FOLDER = os.path.join(
    OUTPUT_FOLDER,
    "reports"
)

THRESHOLD = 80


os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)

os.makedirs(
    OUTPUT_FOLDER,
    exist_ok=True
)

os.makedirs(
    REPORTS_FOLDER,
    exist_ok=True
)


# ============================================================
# JSON CONVERTER
# ============================================================

def json_converter(obj):

    if isinstance(obj, np.integer):
        return int(obj)

    if isinstance(obj, np.floating):
        return float(obj)

    if isinstance(obj, np.ndarray):
        return obj.tolist()

    return str(obj)


# ============================================================
# RESULT JSON PARSER
# ============================================================

def parse_result_json(stdout):

    if not stdout:
        return None

    for line in stdout.splitlines():

        line = line.strip()

        if line.startswith("RESULT_JSON:"):

            try:

                return json.loads(
                    line[len("RESULT_JSON:"):]
                )

            except Exception as error:

                print(
                    "RESULT JSON PARSE ERROR:",
                    error
                )

    return None


# ============================================================
# VERIFY
# ============================================================

@router.post("/verify")
async def verify(

    employee_code: str = Form(...),

    report_id: str = Form(...),

    file: UploadFile = File(...)

):

    print("================================")
    print("VERIFY REQUEST")
    print("Employee :", employee_code)
    print("Report ID :", report_id)
    print("File :", file.filename)
    print("================================")


    temp_files = []


    try:

        # ====================================================
        # VALIDATE REPORT ID
        # ====================================================

        if not report_id:

            return JSONResponse(

                content={
                    "status": False,
                    "message": "Report ID is required"
                },

                status_code=400

            )


        # Prevent path traversal
        safe_report_id = os.path.basename(
            report_id
        )


        if safe_report_id != report_id:

            return JSONResponse(

                content={
                    "status": False,
                    "message": "Invalid report ID"
                },

                status_code=400

            )


        # ====================================================
        # CREATE REPORT FOLDER
        # ====================================================

        report_folder = os.path.join(
            REPORTS_FOLDER,
            safe_report_id
        )


        os.makedirs(
            report_folder,
            exist_ok=True
        )


        print(
            "Report Folder:",
            report_folder
        )


        # ====================================================
        # SAVE UPLOADED IMAGE
        # ====================================================

        extension = os.path.splitext(
            file.filename or ".jpg"
        )[1]


        if not extension:

            extension = ".jpg"


        unique_name = (
            "verify_"
            + uuid.uuid4().hex
            + extension
        )


        file_path = os.path.join(
            UPLOAD_FOLDER,
            unique_name
        )


        with open(
            file_path,
            "wb"
        ) as buffer:

            while True:

                chunk = await file.read(
                    1024 * 1024
                )

                if not chunk:
                    break

                buffer.write(chunk)


        print(
            "Uploaded image saved:",
            file_path
        )


        # ====================================================
        # CREATE YOLO INPUT JSON
        # ====================================================

        yolo_input_file = os.path.join(

            OUTPUT_FOLDER,

            "verify_yolo_"
            + uuid.uuid4().hex
            + ".json"

        )


        with open(
            yolo_input_file,
            "w"
        ) as f:

            json.dump(
                [file_path],
                f
            )


        temp_files.append(
            yolo_input_file
        )


        # ====================================================
        # YOLO BATCH WORKER
        # ====================================================

        yolo_worker = os.path.join(

            os.path.dirname(
                os.path.abspath(__file__)
            ),

            "yolo_batch_worker.py"

        )


        python_executable = os.path.join(

            BASE_DIR,

            "ai-env",
            "bin",
            "python3"

        )


        if not os.path.exists(
            yolo_worker
        ):

            return JSONResponse(

                content={
                    "status": False,
                    "message":
                        "YOLO batch worker not found"
                },

                status_code=500

            )


        print()
        print("================================")
        print("STARTING YOLO SUBPROCESS")
        print("================================")


        worker_env = os.environ.copy()

        worker_env["PYTHONUNBUFFERED"] = "1"

        worker_env["TORCHDYNAMO_DISABLE"] = "1"

        worker_env["CUDA_VISIBLE_DEVICES"] = "-1"

        worker_env["OMP_NUM_THREADS"] = "1"

        worker_env["MKL_NUM_THREADS"] = "1"

        worker_env["OPENBLAS_NUM_THREADS"] = "1"


        yolo_process = (
            await asyncio.create_subprocess_exec(

                python_executable,

                "-X",
                "faulthandler",

                "-u",

                yolo_worker,

                yolo_input_file,

                cwd=BASE_DIR,

                stdout=asyncio.subprocess.PIPE,

                stderr=asyncio.subprocess.PIPE,

                env=worker_env

            )
        )


        yolo_stdout, yolo_stderr = (

            await asyncio.wait_for(

                yolo_process.communicate(),

                timeout=300

            )

        )


        yolo_stdout = yolo_stdout.decode(
            "utf-8",
            errors="replace"
        )


        yolo_stderr = yolo_stderr.decode(
            "utf-8",
            errors="replace"
        )


        print(
            "YOLO Return Code:",
            yolo_process.returncode
        )


        if yolo_stdout:

            print(
                "===== YOLO STDOUT ====="
            )

            print(
                yolo_stdout
            )


        if yolo_stderr:

            print(
                "===== YOLO STDERR ====="
            )

            print(
                yolo_stderr
            )


        yolo_result = parse_result_json(
            yolo_stdout
        )


        # ====================================================
        # YOLO FAILED
        # ====================================================

        if (

            yolo_process.returncode != 0

            or

            yolo_result is None

        ):

            return JSONResponse(

                content={

                    "status": False,

                    "message":
                        "YOLO detection failed",

                    "worker_code":
                        yolo_process.returncode,

                    "worker_error":
                        yolo_stderr[-2000:]

                },

                status_code=200

            )


        yolo_items = yolo_result.get(
            "results",
            []
        )


        if not yolo_items:

            return JSONResponse(

                content={
                    "status": False,
                    "message":
                        "No iris detected"
                },

                status_code=200

            )


        successful_yolo = None


        for item in yolo_items:

            if item.get("success"):

                successful_yolo = item

                break


        if successful_yolo is None:

            return JSONResponse(

                content={
                    "status": False,
                    "message":
                        "No iris detected"
                },

                status_code=200

            )


        detection = successful_yolo.get(
            "result"
        )


        if not detection:

            return JSONResponse(

                content={
                    "status": False,
                    "message":
                        "YOLO result missing"
                },

                status_code=200

            )


        crop_path = detection.get(
            "crop_path"
        )


        if not crop_path:

            return JSONResponse(

                content={
                    "status": False,
                    "message":
                        "YOLO crop path missing"
                },

                status_code=200

            )


        if not os.path.isabs(
            crop_path
        ):

            crop_path = os.path.join(
                BASE_DIR,
                crop_path
            )


        if not os.path.exists(
            crop_path
        ):

            return JSONResponse(

                content={
                    "status": False,
                    "message":
                        "Cropped iris image not found"
                },

                status_code=200

            )


        print(
            "YOLO CROP:",
            crop_path
        )


        # ====================================================
        # CREATE VISION INPUT JSON
        # ====================================================

        vision_input_file = os.path.join(

            OUTPUT_FOLDER,

            "verify_vision_"
            + uuid.uuid4().hex
            + ".json"

        )


        vision_items = [

            {

                "image": file_path,

                "crop_path": crop_path

            }

        ]


        with open(
            vision_input_file,
            "w"
        ) as f:

            json.dump(
                vision_items,
                f
            )


        temp_files.append(
            vision_input_file
        )


        # ====================================================
        # VISION BATCH WORKER
        # ====================================================

        vision_worker = os.path.join(

            BASE_DIR,

            "api",

            "vision_batch_worker.py"

        )


        if not os.path.exists(
            vision_worker
        ):

            return JSONResponse(

                content={
                    "status": False,
                    "message":
                        "Vision batch worker not found"
                },

                status_code=500

            )


        print()
        print("================================")
        print("STARTING VISION SUBPROCESS")
        print("================================")


        vision_env = os.environ.copy()

        vision_env["PYTHONUNBUFFERED"] = "1"

        vision_env["CUDA_VISIBLE_DEVICES"] = "-1"

        vision_env["OMP_NUM_THREADS"] = "1"

        vision_env["MKL_NUM_THREADS"] = "1"

        vision_env["OPENBLAS_NUM_THREADS"] = "1"

        vision_env["TF_NUM_INTRAOP_THREADS"] = "1"

        vision_env["TF_NUM_INTEROP_THREADS"] = "1"


        vision_process = (

            await asyncio.create_subprocess_exec(

                python_executable,

                "-X",
                "faulthandler",

                "-u",

                vision_worker,

                vision_input_file,

                cwd=BASE_DIR,

                stdout=asyncio.subprocess.PIPE,

                stderr=asyncio.subprocess.PIPE,

                env=vision_env

            )

        )


        vision_stdout, vision_stderr = (

            await asyncio.wait_for(

                vision_process.communicate(),

                timeout=600

            )

        )


        vision_stdout = vision_stdout.decode(
            "utf-8",
            errors="replace"
        )


        vision_stderr = vision_stderr.decode(
            "utf-8",
            errors="replace"
        )


        print(
            "Vision Return Code:",
            vision_process.returncode
        )


        if vision_stdout:

            print(
                "===== VISION STDOUT ====="
            )

            print(
                vision_stdout
            )


        if vision_stderr:

            print(
                "===== VISION STDERR ====="
            )

            print(
                vision_stderr
            )


        vision_result = parse_result_json(
            vision_stdout
        )


        # ====================================================
        # VISION FAILED
        # ====================================================

        if (

            vision_process.returncode != 0

            or

            vision_result is None

        ):

            return JSONResponse(

                content={

                    "status": False,

                    "message":
                        "Vision processing failed",

                    "worker_code":
                        vision_process.returncode,

                    "worker_error":
                        vision_stderr[-2000:]

                },

                status_code=200

            )


        # ====================================================
        # NORMALIZE VISION WORKER RESULT
        # ====================================================

        vision_items_result = vision_result.get(
            "items",
            []
        )

        # Support batch workers returning "results"
        if not vision_items_result:
            vision_items_result = vision_result.get(
                "results",
                []
            )

        # Support a single direct result object
        if not vision_items_result:
            single_result = vision_result.get(
                "result"
            )

            if isinstance(single_result, dict):
                vision_items_result = [
                    {
                        "success": True,
                        "result": single_result
                    }
                ]

        # Support vision result returned directly
        if (
            isinstance(vision_result, dict)
            and (
                vision_result.get("cnn_embedding") is not None
                or vision_result.get("embedding") is not None
            )
        ):
            vision_items_result = [
                {
                    "success": True,
                    "result": vision_result
                }
            ]

        if not isinstance(
            vision_items_result,
            list
        ):
            vision_items_result = []

        if not vision_items_result:
            return JSONResponse(
                content={
                    "status": False,
                    "message":
                        "Vision result missing"
                },
                status_code=200
            )

        successful_vision = None

        for item in vision_items_result:

            if not isinstance(item, dict):
                continue

            if item.get("success") is True:
                successful_vision = item
                break

            # Direct result object
            if (
                item.get("cnn_embedding") is not None
                or item.get("embedding") is not None
            ):
                successful_vision = {
                    "success": True,
                    "result": item
                }
                break

        if successful_vision is None:

            return JSONResponse(

                content={
                    "status": False,
                    "message":
                        "Iris vision processing failed"
                },

                status_code=200

            )


        vision_data = successful_vision.get(
            "result"
        )


        if not vision_data:

            return JSONResponse(

                content={
                    "status": False,
                    "message":
                        "Vision result missing"
                },

                status_code=200

            )


        # ====================================================
        # GET CNN EMBEDDING
        # ====================================================

        embedding = vision_data.get(
            "cnn_embedding"
        )


        if embedding is None:

            embedding = vision_data.get(
                "embedding"
            )


        if not embedding:

            return JSONResponse(

                content={
                    "status": False,
                    "message":
                        "CNN embedding missing"
                },

                status_code=200

            )


        print(
            "CNN EMBEDDING SUCCESS"
        )


        print(
            "Embedding Length:",
            len(embedding)
        )


        # ====================================================
        # LOAD EMPLOYEE
        # ====================================================

        user = get_user(
            employee_code
        )


        if user is None:

            return JSONResponse(

                content={
                    "status": False,
                    "message":
                        "Employee not found"
                },

                status_code=200

            )


        # ====================================================
        # LOAD SAVED EMBEDDINGS
        # ====================================================

        embeddings = get_embeddings(
            employee_code
        )


        if len(embeddings) == 0:

            embeddings = [
                user["embedding"]
            ]


        current_embedding = np.array(
            embedding,
            dtype=np.float32
        )


        best_score = -1


        for saved_embedding in embeddings:

            if isinstance(
                saved_embedding,
                str
            ):

                saved_embedding = json.loads(
                    saved_embedding
                )


            saved_embedding = np.array(
                saved_embedding,
                dtype=np.float32
            )


            score = cosine_similarity(

                current_embedding,

                saved_embedding

            )


            if score > best_score:

                best_score = score


        best_employee = user


        # ====================================================
        # FINAL SIMILARITY
        # ====================================================

        similarity = round(
            best_score * 100,
            2
        )


        matched = (
            similarity >= THRESHOLD
        )


        # ====================================================
        # EMPLOYEE IMAGES
        # ====================================================

        images = get_employee_images(

            best_employee[
                "employee_code"
            ]

        )


        # ====================================================
        # RESPONSE
        # ====================================================

        response = {

            "status": True,

            "report_id":
                safe_report_id,

            "matched":
                matched,

            "match_status":
                "Matched"
                if matched
                else "Not Matched",

            "similarity":
                similarity,

            "confidence":
                similarity,

            "threshold":
                THRESHOLD,

            "employee": {

                "employee_code":
                    best_employee[
                        "employee_code"
                    ],

                "employee_name":
                    best_employee[
                        "user_name"
                    ],

                "department":
                    best_employee[
                        "department"
                    ],

                "designation":
                    best_employee[
                        "designation"
                    ],

                "gender":
                    best_employee[
                        "gender"
                    ],

                "age":
                    best_employee[
                        "age"
                    ],

                "dob":
                    best_employee[
                        "dob"
                    ],

                "blood_group":
                    best_employee[
                        "blood_group"
                    ],

                "mobile":
                    best_employee[
                        "mobile"
                    ],

                "email":
                    best_employee[
                        "email"
                    ],

                "address":
                    best_employee[
                        "address"
                    ],

                "photo_path":
                    best_employee[
                        "photo_path"
                    ],

                "images":
                    images
            }

        }


        safe_response = json.loads(

            json.dumps(

                response,

                default=json_converter

            )

        )


        # ====================================================
        # SAVE VERIFY RESULT
        # PER REPORT FOLDER
        # ====================================================

        verify_file = os.path.join(

            report_folder,

            "verify.json"

        )


        with open(
            verify_file,
            "w"
        ) as f:

            json.dump(

                safe_response,

                f,

                indent=4

            )


        # ====================================================
        # SAVE VISION RESULT
        # ====================================================

        vision_file = os.path.join(

            report_folder,

            "vision.json"

        )


        with open(
            vision_file,
            "w"
        ) as f:

            json.dump(

                vision_data,

                f,

                default=json_converter,

                indent=4

            )


        # ====================================================
        # SAVE DETECTION RESULT
        # ====================================================

        detect_data = {

            "status": True,

            "report_id":
                safe_report_id,

            "employee_code":
                employee_code,

            "detection":
                detection,

            "crop_path":
                detection.get(
                    "crop_path"
                ),

            "images":
                vision_data.get(
                    "images",
                    {}
                ),

            "eye_side":
                vision_data.get(
                    "eye_side"
                ),

            "features":
                vision_data.get(
                    "features",
                    {}
                ),

            "entropy":
                vision_data.get(
                    "entropy"
                ),

            "color_analysis":
                vision_data.get(
                    "color_analysis"
                ),

            "glcm":
                vision_data.get(
                    "glcm"
                )

        }


        safe_detect = json.loads(

            json.dumps(

                detect_data,

                default=json_converter

            )

        )


        detect_file = os.path.join(

            report_folder,

            "detect.json"

        )


        with open(
            detect_file,
            "w"
        ) as f:

            json.dump(

                safe_detect,

                f,

                indent=4

            )


        # ====================================================
        # SAVE REPORT META
        # ====================================================

        report_meta = {

            "report_id":
                safe_report_id,

            "employee_code":
                employee_code,

            "created_at":
                __import__(
                    "datetime"
                ).datetime.now().isoformat()

        }


        with open(

            os.path.join(
                report_folder,
                "meta.json"
            ),

            "w"

        ) as f:

            json.dump(

                report_meta,

                f,

                indent=4

            )


        print()
        print("================================")
        print("VERIFY COMPLETED")
        print("Report ID :", safe_report_id)
        print("Similarity :", similarity)
        print("Matched :", matched)
        print("Report Folder :", report_folder)
        print("================================")


        return JSONResponse(
            content=safe_response
        )


    except asyncio.TimeoutError:

        print(
            "VERIFY WORKER TIMEOUT"
        )


        return JSONResponse(

            content={

                "status": False,

                "message":
                    "Verification processing timeout"

            },

            status_code=200

        )


    except Exception as ex:

        traceback.print_exc()


        return JSONResponse(

            content={

                "status": False,

                "message":
                    str(ex)

            },

            status_code=500

        )


    finally:

        # ====================================================
        # CLEAN TEMP JSON FILES
        # ====================================================

        for path in temp_files:

            try:

                if os.path.exists(
                    path
                ):

                    os.remove(
                        path
                    )

            except Exception:

                pass