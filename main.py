from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.detect import router
from api.enroll import router as enroll_router
from api.verify import router as verify_router
from api.report import router as report_router
from api.dashboard import router as dashboard_router
from api.register_frame import router as register_frame_router

from database import create_database


app = FastAPI(
    title="Iris AI API",
    version="1.0.0"
)

# ---------------- Static Files ----------------

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)

app.mount(
    "/outputs",
    StaticFiles(directory="outputs"),
    name="outputs"
)

app.mount(
    "/uploads",
    StaticFiles(directory="uploads"),
    name="uploads"
)

# ---------------- Database ----------------

create_database()

# ---------------- CORS ----------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- APIs ----------------

app.include_router(router)
app.include_router(enroll_router)
app.include_router(verify_router)
app.include_router(report_router)
app.include_router(dashboard_router)
app.include_router(register_frame_router)
# ---------------- Home ----------------

@app.get("/")
def home():
    return {
        "status": True,
        "message": "Iris AI API Running Successfully"
    }

# ---------------- Health ----------------

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }