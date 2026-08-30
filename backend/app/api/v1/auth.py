import uuid
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, Depends, status
from pymongo.database import Database
from backend.app.core.database import get_db
from backend.app.core.errors import AppError, AuthRequiredError
from backend.app.auth.schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    UserResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from backend.app.auth.security import (
    verify_password,
    get_password_hash,
    create_access_token,
)
from backend.app.auth.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(req: UserRegisterRequest, db: Database = Depends(get_db)):
    existing = db.users.find_one({"email": req.email.lower()})
    if existing:
        raise AppError(status.HTTP_400_BAD_REQUEST, "USER_EXISTS", "A user with this email already exists")

    user_count = db.users.count_documents({})
    role = "super-admin" if user_count == 0 else (req.role or "user")

    user_id = str(uuid.uuid4())
    user_doc = {
        "id": user_id,
        "name": req.name,
        "email": req.email.lower(),
        "hashed_password": get_password_hash(req.password),
        "role": role,
        "department_id": req.department_id,
        "status": "active",
        "auth_provider": "local",
        "created_at": datetime.utcnow(),
        "last_login_at": datetime.utcnow(),
    }
    db.users.insert_one(user_doc)

    token = create_access_token(user_id)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=user_id,
        role=role,
        name=req.name,
        email=req.email.lower(),
    )


@router.post("/login", response_model=TokenResponse)
def login(req: UserLoginRequest, background_tasks: BackgroundTasks, db: Database = Depends(get_db)):
    user = db.users.find_one({"email": req.email.lower()})
    if not user or not verify_password(req.password, user.get("hashed_password", "")):
        raise AuthRequiredError("Incorrect email or password")

    if user.get("status") != "active":
        raise AppError(status.HTTP_403_FORBIDDEN, "FORBIDDEN", "Account suspended")

    background_tasks.add_task(db.users.update_one, {"id": user["id"]}, {"$set": {"last_login_at": datetime.utcnow()}})

    token = create_access_token(user["id"])
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=user["id"],
        role=user.get("role", "user"),
        name=user.get("name", "User"),
        email=user["email"],
    )


@router.post("/logout")
def logout(current_user: Dict[str, Any] = Depends(get_current_user)):
    return {"message": "Successfully logged out"}


@router.get("/me")
def get_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    return {
        "id": current_user["id"],
        "name": current_user.get("name", ""),
        "email": current_user.get("email", ""),
        "role": current_user.get("role", "user"),
        "department_id": current_user.get("department_id"),
        "status": current_user.get("status", "active"),
        "created_at": current_user.get("created_at", datetime.utcnow()),
        "last_login_at": current_user.get("last_login_at"),
    }


@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest, db: Database = Depends(get_db)):
    user = db.users.find_one({"email": req.email.lower()})
    if user:
        token = create_access_token(f"reset:{user['id']}")
        return {"message": "Password reset token generated", "reset_token": token}
    return {"message": "If the email is registered, reset instructions have been generated"}


@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest, db: Database = Depends(get_db)):
    user = db.users.find_one({"email": req.email.lower()})
    if not user:
        raise AppError(status.HTTP_404_NOT_FOUND, "USER_NOT_FOUND", "User not found")
    db.users.update_one(
        {"id": user["id"]},
        {"$set": {"hashed_password": get_password_hash(req.new_password)}}
    )
    return {"message": "Password updated successfully"}
