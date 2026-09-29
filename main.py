from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from api.detect import router
from api.enroll import router as enroll_router
from api.verify import router as verify_router
from api.report import router as report_router
from api.dashboard import router as dashboard_router
from api.register_frame import router as register_frame_router
from api.profile import router as profile_router
from api.quality import router as quality_router
from api.auth import router as auth_router
from api.media import router as media_router
from api.students import router as students_router
from api.assessments import router as assessments_router
from api.scans import router as scans_router
from api.analysis import router as analysis_router
from api.official_report import router as official_report_router
from api.counsellor import router as counsellor_router
from api.student_portal import router as student_portal_router
from api.admin_portal import router as admin_portal_router

from database import create_database
from database_student import create_student_tables
from security.auth import init_auth_db
from security.cors_config import get_cors_configuration
import os

is_production = os.environ.get("ENVIRONMENT", os.environ.get("ENV", "development")).lower().strip() == "production"
docs_enabled = os.environ.get("ENABLE_DOCS", "false" if is_production else "true").lower() in ("true", "1")

app = FastAPI(
    title="Iris AI API",
    version="1.0.0",
    docs_url="/docs" if docs_enabled else None,
    redoc_url="/redoc" if docs_enabled else None,
    openapi_url="/openapi.json" if docs_enabled else None,
)

# ---------------- Static Files (UI Assets Only) ----------------
# Note: Raw biometric uploads and outputs are no longer mounted publicly.
# Media is securely accessed through the authenticated /api/media endpoints.

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)

from database_official import init_official_tables

# ---------------- Database Initialization ----------------

create_database()
create_student_tables()
init_auth_db()
init_official_tables()

# ---------------- Security Headers ----------------

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(self)"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# ---------------- Hardened CORS ----------------

cors_origins, cors_credentials = get_cors_configuration()

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=cors_credentials,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ---------------- APIs ----------------

app.include_router(auth_router)
app.include_router(media_router)
app.include_router(router)
app.include_router(enroll_router)
app.include_router(verify_router)
app.include_router(report_router)
app.include_router(dashboard_router)
app.include_router(register_frame_router)
app.include_router(profile_router)
app.include_router(quality_router)
app.include_router(students_router)
app.include_router(assessments_router)
app.include_router(scans_router)
app.include_router(analysis_router)
app.include_router(official_report_router)
app.include_router(counsellor_router)
app.include_router(student_portal_router)
app.include_router(admin_portal_router)

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