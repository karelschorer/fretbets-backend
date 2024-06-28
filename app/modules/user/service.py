from sqlalchemy.orm import Session
from .models import User
from .utils import hash_password
from fastapi import HTTPException, status
from pydantic import EmailStr
import uuid

def create_user(db: Session, username: str, email: EmailStr, password: str):
    # Check if username or email already exists
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    hashed_password = hash_password(password)
    verification_token = str(uuid.uuid4())

    user = User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        verification_token=verification_token,
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()

def get_user_by_email(db: Session, email: EmailStr):
    return db.query(User).filter(User.email == email).first()
