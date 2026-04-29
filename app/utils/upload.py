import os
import shutil
from pathlib import Path
from fastapi import UploadFile, HTTPException
from app.core.config import settings

def save_upload_file(upload_file: UploadFile, sub_path: str) -> str:
    """
    Save uploaded file to local storage or firebase.
    Return the relative path to be stored in DB.
    sub_path example: {org_uuid}/organization_images
    """
    if settings.STORAGE_TYPE == "local":
        return _save_local(upload_file, sub_path)
    elif settings.STORAGE_TYPE == "firebase":
        return _save_firebase(upload_file, sub_path)
    else:
        # Default to local
        return _save_local(upload_file, sub_path)

import time

def _save_local(upload_file: UploadFile, sub_path: str) -> str:
    base_dir = Path(settings.UPLOAD_DIR)
    
    # Path: uploads/{sub_path}/{filename}
    target_dir = base_dir / sub_path
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename with timestamp
    timestamp = int(time.time() * 1000) # ms
    ext = Path(upload_file.filename).suffix
    if not ext:
        ext = ".png" # default fallback
        
    filename = f"{timestamp}{ext}"
    file_path = target_dir / filename
    
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
        
    return f"{sub_path}/{filename}"

def _save_firebase(upload_file: UploadFile, sub_path: str) -> str:
    # Placeholder for Firebase implementation
    # Would upload to simple storage bucket and return URL or path
    # For now just raise not implemented or fallback
    print("Firebase storage not implemented, falling back to local mock")
    return _save_local(upload_file, sub_path)

def get_file_url(file_path: str) -> str:
    if not file_path:
        return None
        
    if settings.STORAGE_TYPE == "local":
        return f"{settings.SERVER_HOST}/static/{file_path}"
    elif settings.STORAGE_TYPE == "firebase":
        # If we stored full URL
        if file_path.startswith("http"):
            return file_path
        # If we stored path, construct it
        return f"https://firebasestorage.googleapis.com/.../{file_path}"
    
    return file_path

def delete_file(file_path: str):
    """
    Delete file from storage.
    file_path: relative path stored in DB.
    """
    if not file_path:
        return
        
    if settings.STORAGE_TYPE == "local":
        _delete_local(file_path)
    elif settings.STORAGE_TYPE == "firebase":
        _delete_firebase(file_path)
    else:
        _delete_local(file_path)

def _delete_local(file_path: str):
    base_dir = Path(settings.UPLOAD_DIR)
    target_file = base_dir / file_path
    if target_file.exists():
        try:
            os.remove(target_file)
        except Exception as e:
            print(f"Error deleting file {target_file}: {e}")

def _delete_firebase(file_path: str):
    # Placeholder
    print(f"Mock deleting firebase file: {file_path}")
    pass
