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

from database import create_database
from database_student import create_student_tables
from security.auth import init_auth_db
from security.cors_config import get_cors_configuration


app = FastAPI(
    title="Iris AI API",
    version="1.0.0"
)

# ---------------- Static Files (UI Assets Only) ----------------
# Note: Raw biometric uploads and outputs are no longer mounted publicly.
# Media is securely accessed through the authenticated /api/media endpoints.

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)

# ---------------- Database Initialization ----------------

create_database()
create_student_tables()
init_auth_db()

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
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
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