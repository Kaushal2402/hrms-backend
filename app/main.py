import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.api.v1.api import api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    swagger_ui_parameters={"persistAuthorization": True}
)

# Ensure upload directory exists
try:
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
except OSError:
    pass

# Ensure mock directory exists for development
MOCK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mock_files")
try:
    os.makedirs(MOCK_DIR, exist_ok=True)
except OSError:
    pass

# Mount Static Files
if os.path.exists(settings.UPLOAD_DIR):
    app.mount("/static", StaticFiles(directory=settings.UPLOAD_DIR), name="static")
if os.path.exists(MOCK_DIR):
    app.mount("/mock", StaticFiles(directory=MOCK_DIR), name="mock")

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        clean_error = {
            "type": error.get("type"),
            "loc": error.get("loc"),
            "msg": error.get("msg"),
        }
        errors.append(clean_error)
        
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "Validation Error",
            "data": None,
            "errors": errors 
        },
    )

from fastapi.exceptions import HTTPException
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": str(exc.detail) if isinstance(exc.detail, (str, int, float)) else "Error occurred",
            "data": None,
            "errors": exc.detail if not isinstance(exc.detail, (str, int, float)) else []
        },
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal Server Error",
            "data": None,
            "errors": [str(exc)]
        },
    )

@app.get("/")
def root():
    return {"message": "Welcome to HRMS Backend API"}
