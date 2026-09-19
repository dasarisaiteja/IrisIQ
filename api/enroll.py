
from fastapi import APIRouter, UploadFile, File, Form

import shutil
import os
import glob
import json
import subprocess
import asyncio

from datetime import datetime

from database import enroll_user


router = APIRouter()


# ============================================================
# FOLDERS
# ============================================================

UPLOAD_FOLDER = "uploads"
PHOTO_FOLDER = "static/photos"
TRAIN_FOLDER = "training_dataset"


os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)

os.makedirs(
    PHOTO_FOLDER,
    exist_ok=True
)

os.makedirs(
    TRAIN_FOLDER,
    exist_ok=True
)


# ============================================================
# ENROLL
# ============================================================

@router.post("/enroll")
async def enroll(

    employee_code: str = Form(...),

    user_name: str = Form(...),

    department: str = Form(...),

    designation: str = Form(...),

    gender: str = Form(...),

    age: int = Form(...),

    dob: str = Form(...),

    blood_group: str = Form(...),

    mobile: str = Form(...),

    email: str = Form(...),

    address: str = Form(...),

    file: UploadFile = File(...)

):

    print("=" * 70)
    print("EMPLOYEE ENROLL STARTED")
    print("=" * 70)

    print("Employee Code :", employee_code)
    print("Employee Name :", user_name)

    # ========================================================
    # SAVE PHOTO
    # ========================================================

    employee_folder = os.path.join(
        PHOTO_FOLDER,
        employee_code
    )

    os.makedirs(
        employee_folder,
        exist_ok=True
    )

    photo_name = datetime.now().strftime(
        "%Y%m%d%H%M%S"
    ) + ".jpg"

    photo_path = os.path.join(
        employee_folder,
        photo_name
    )

    try:

        with open(
            photo_path,
            "wb"
        ) as buffer:

            shutil.copyfileobj(
                file.file,
                buffer
            )

    except Exception as error:

        print(
            "PHOTO SAVE ERROR :",
            error
        )

        return {

            "status": False,

            "message":
                "Employee photo could not be saved",

            "employee_code":
                employee_code,

            "error":
                str(error)

        }

    print(
        "Photo Saved :",
        photo_path
    )

    # ========================================================
    # COPY REGISTERED IMAGES
    # ========================================================

    upload_folder = os.path.join(
        UPLOAD_FOLDER,
        employee_code
    )

    training_folder = os.path.join(
        TRAIN_FOLDER,
        employee_code
    )

    os.makedirs(
        training_folder,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Support JPG / JPEG / PNG
    # --------------------------------------------------------

    images = []

    for extension in (
        "*.jpg",
        "*.jpeg",
        "*.png"
    ):

        images.extend(
            glob.glob(
                os.path.join(
                    upload_folder,
                    extension
                )
            )
        )

    images.sort()

    print(
        "Registered Images Found :",
        len(images)
    )

    # ========================================================
    # COPY IMAGES TO TRAINING DATASET
    # ========================================================

    for img in images:

        try:

            shutil.copy2(
                img,
                os.path.join(
                    training_folder,
                    os.path.basename(img)
                )
            )

        except Exception as error:

            print(
                "Training Image Copy ERROR :",
                img,
                error
            )

    print(
        "Training Images :",
        len(images)
    )

    # ========================================================
    # NO IMAGES
    # ========================================================

    if not images:

        return {

            "status": False,

            "message":
                "No registered images found",

            "employee_code":
                employee_code

        }

    # ========================================================
    # START AI WORKER
    # ========================================================

    print("=" * 70)
    print(
        "STARTING AI ENROLLMENT WORKER"
    )
    print("=" * 70)

    worker_script = os.path.join(
        os.path.dirname(
            os.path.abspath(__file__)
        ),
        "enroll_worker.py"
    )

    # ========================================================
    # PYTHON PATH
    # ========================================================

    python_path = os.path.join(

        os.path.dirname(
            os.path.dirname(
                os.path.abspath(__file__)
            )
        ),

        "ai-env",
        "bin",
        "python3"

    )

    # ========================================================
    # CHECK PYTHON
    # ========================================================

    if not os.path.exists(
        python_path
    ):

        print(
            "ERROR: Python executable not found:"
        )

        print(
            python_path
        )

        return {

            "status": False,

            "message":
                "AI Python environment not found",

            "employee_code":
                employee_code

        }

    # ========================================================
    # CHECK WORKER
    # ========================================================

    if not os.path.exists(
        worker_script
    ):

        print(
            "ERROR: Enrollment worker not found:"
        )

        print(
            worker_script
        )

        return {

            "status": False,

            "message":
                "AI enrollment worker not found",

            "employee_code":
                employee_code

        }

    # ========================================================
    # WORKER COMMAND
    # ========================================================

    worker_command = [

        python_path,

        "-X",

        "faulthandler",

        "-u",

        worker_script,

        employee_code

    ]

    print(
        "Worker Command :",
        worker_command
    )

    print(
        "Worker CWD :",
        os.path.dirname(
            os.path.dirname(
                os.path.abspath(__file__)
            )
        )
    )

    # ========================================================
    # AI ENVIRONMENT
    # ========================================================

    worker_env = os.environ.copy()

    worker_env["PYTHONUNBUFFERED"] = "1"

    worker_env["TORCHDYNAMO_DISABLE"] = "1"

    worker_env["CUDA_VISIBLE_DEVICES"] = "-1"

    worker_env["OMP_NUM_THREADS"] = "1"

    worker_env["MKL_NUM_THREADS"] = "1"

    worker_env["OPENBLAS_NUM_THREADS"] = "1"

    worker_env["TF_NUM_INTRAOP_THREADS"] = "1"

    worker_env["TF_NUM_INTEROP_THREADS"] = "1"

    # ========================================================
    # RUN AI WORKER
    #
    # IMPORTANT:
    #
    # subprocess.run() was blocking the FastAPI event loop.
    #
    # create_subprocess_exec() allows FastAPI/Uvicorn to
    # continue handling other requests while AI processing
    # is running.
    # ========================================================

    try:

        worker_process = await asyncio.create_subprocess_exec(

            *worker_command,

            cwd=os.path.dirname(
                os.path.dirname(
                    os.path.abspath(__file__)
                )
            ),

            stdout=asyncio.subprocess.PIPE,

            stderr=asyncio.subprocess.PIPE,

            env=worker_env

        )

        print(
            "AI Worker PID :",
            worker_process.pid
        )

        stdout, stderr = await worker_process.communicate()

        worker_stdout = stdout.decode(
            "utf-8",
            errors="replace"
        )

        worker_stderr = stderr.decode(
            "utf-8",
            errors="replace"
        )

        worker_return_code = (
            worker_process.returncode
        )

    except Exception as error:

        print(
            "WORKER START ERROR :",
            error
        )

        return {

            "status": False,

            "message":
                "AI enrollment worker could not start",

            "employee_code":
                employee_code,

            "error":
                str(error)

        }

    # ========================================================
    # WORKER RESULT
    # ========================================================

    print(
        "Worker Return Code :",
        worker_return_code
    )

    print(
        "===== WORKER STDOUT ====="
    )

    print(
        worker_stdout
    )

    print(
        "===== WORKER STDERR ====="
    )

    print(
        worker_stderr
    )

    # ========================================================
    # WORKER FAILED
    # ========================================================

    if worker_return_code != 0:

        print(
            "=" * 70
        )

        print(
            "AI ENROLLMENT WORKER FAILED"
        )

        print(
            "Return Code :",
            worker_return_code
        )

        print(
            "=" * 70
        )

        return {

            "status": False,

            "message":
                "AI enrollment worker failed",

            "employee_code":
                employee_code,

            "worker_return_code":
                worker_return_code,

            "worker_error":
                worker_stderr[-5000:]

        }

    # ========================================================
    # READ LAST EMBEDDING
    # ========================================================

    last_embedding_file = os.path.join(

        "outputs",

        "enrollment",

        employee_code +
        "_last_embedding.json"

    )

    last_embedding = None

    # ========================================================
    # CHECK LAST EMBEDDING FILE
    # ========================================================

    if os.path.exists(
        last_embedding_file
    ):

        try:

            with open(
                last_embedding_file,
                "r"
            ) as f:

                data = json.load(
                    f
                )

                last_embedding = data.get(
                    "embedding"
                )

        except Exception as error:

            print(
                "Last embedding read error :",
                error
            )

    # ========================================================
    # EMBEDDING NOT FOUND
    # ========================================================

    if last_embedding is None:

        return {

            "status": False,

            "message":
                "AI processing completed but embedding was not found",

            "employee_code":
                employee_code

        }

    # ========================================================
    # VALIDATE EMBEDDING
    # ========================================================

    if not isinstance(
        last_embedding,
        list
    ):

        print(
            "ERROR: Invalid embedding format"
        )

        return {

            "status": False,

            "message":
                "Invalid AI embedding generated",

            "employee_code":
                employee_code

        }

    if len(last_embedding) == 0:

        print(
            "ERROR: Empty embedding"
        )

        return {

            "status": False,

            "message":
                "Empty AI embedding generated",

            "employee_code":
                employee_code

        }

    print(
        "Last Embedding Length :",
        len(last_embedding)
    )

    # ========================================================
    # SAVE EMPLOYEE
    # ========================================================

    print(
        "\nSTEP 5 : Save Employee"
    )

    try:

        enroll_user(

            employee_code,

            user_name,

            department,

            designation,

            gender,

            age,

            dob,

            blood_group,

            mobile,

            email,

            address,

            photo_path,

            last_embedding

        )

    except Exception as error:

        print(
            "Employee Save ERROR :",
            error
        )

        return {

            "status": False,

            "message":
                "Employee could not be saved",

            "employee_code":
                employee_code,

            "error":
                str(error)

        }

    print(
        "Employee Saved Successfully"
    )

    # ========================================================
    # VERIFY TRAINING DATASET
    # ========================================================

    total_training = 0

    for extension in (
        "*.jpg",
        "*.jpeg",
        "*.png"
    ):

        total_training += len(

            glob.glob(

                os.path.join(

                    training_folder,

                    extension

                )

            )

        )

    print(
        "Total Images :",
        total_training
    )

    if total_training < 40:

        print(
            "WARNING : Less than 40 images available"
        )

    else:

        print(
            "Training Dataset Ready"
        )

    # ========================================================
    # SUCCESS
    # ========================================================

    print(
        "=" * 70
    )

    print(
        "EMPLOYEE ENROLL COMPLETED"
    )

    print(
        "=" * 70
    )

    # ========================================================
    # FINAL RESPONSE
    # ========================================================

    return {

        "status": True,

        "message":
            "Employee Registered Successfully",

        "employee": {

            "employee_code":
                employee_code,

            "employee_name":
                user_name,

            "department":
                department,

            "designation":
                designation,

            "gender":
                gender,

            "age":
                age,

            "dob":
                dob,

            "blood_group":
                blood_group,

            "mobile":
                mobile,

            "email":
                email,

            "address":
                address,

            "photo":
                photo_path,

            "training_images":
                total_training,

            "embedding_size":
                len(last_embedding)

        }

    }
