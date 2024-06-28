from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field, validator
from app.database import get_db
from .service import create_user
from .utils import send_verification_email, verify_password, create_access_token
from .models import User
from app.dependencies import get_current_user

import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class UserLogin(BaseModel):
    email: EmailStr
    password: str
    
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, regex="^[a-zA-Z0-9_]+$")
    email: EmailStr
    password: str = Field(..., min_length=8)

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one digit')
        if not any(char.isalpha() for char in v):
            raise ValueError('Password must contain at least one letter')
        return v

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(user: UserCreate, db: Session = Depends(get_db)):
    created_user = create_user(db, user.username, user.email, user.password)
    send_verification_email(created_user.email, created_user.verification_token)
    return {"id": created_user.id, "username": created_user.username, "email": created_user.email, "is_verified": created_user.is_verified}

@router.get("/verify-email", status_code=status.HTTP_200_OK)
def verify_email(token: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.verification_token == token).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")

    logger.info(f"User found: {user.username}, is_verified: {user.is_verified}")

    user.is_verified = True
    user.verification_token = None
    db.commit()
    db.refresh(user)

    logger.info(f"User updated: {user.username}, is_verified: {user.is_verified}")

    return {"message": "Email verified successfully"}

@router.post("/login", status_code=status.HTTP_200_OK)
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email or password")

    if not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email or password")

    if not db_user.is_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email not verified")

    access_token = create_access_token(data={"sub": db_user.email})
    
    logger.info(f"User logged in: {db_user.username}")

    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/profile", status_code=status.HTTP_200_OK)
def get_profile(current_user: User = Depends(get_current_user)):
    return {"email": current_user.email}