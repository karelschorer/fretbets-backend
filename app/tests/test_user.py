import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.main import app
from app.modules.user.models import User
from app.modules.user.utils import create_access_token, hash_password

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

# Dependency override
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(scope="module")
def db():
    Base.metadata.create_all(bind=engine)
    yield TestingSessionLocal()
    Base.metadata.drop_all(bind=engine)

def test_register_user(db):
    response = client.post("/api/register", json={
        "username": "testuser",
        "email": "testuser@example.com",
        "password": "testpassword123"
    })
    assert response.status_code == 201
    assert response.json()["username"] == "testuser"
    assert response.json()["email"] == "testuser@example.com"
    assert not response.json()["is_verified"]

def test_verify_email(db):
    user = db.query(User).filter(User.username == "testuser").first()
    assert user
    token = user.verification_token

    response = client.get(f"/api/verify-email?token={token}")
    assert response.status_code == 200
    assert response.json()["message"] == "Email verified successfully"

    # Explicitly refresh the user object to get the latest state
    db.refresh(user)
    user = db.query(User).filter(User.username == "testuser").first()
    assert user.is_verified

def test_register_existing_username(db):
    response = client.post("/api/register", json={
        "username": "testuser",
        "email": "anotheremail@example.com",
        "password": "testpassword123"
    })
    assert response.status_code == 400
    assert response.json()["detail"] == "Username already taken"

def test_register_existing_email(db):
    response = client.post("/api/register", json={
        "username": "newuser",
        "email": "testuser@example.com",
        "password": "testpassword123"
    })
    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"

def test_register_invalid_email(db):
    response = client.post("/api/register", json={
        "username": "anotheruser",
        "email": "invalidemail",
        "password": "testpassword123"
    })
    assert response.status_code == 422

def test_register_weak_password(db):
    response = client.post("/api/register", json={
        "username": "weakpassworduser",
        "email": "weakpassworduser@example.com",
        "password": "12345678"
    })
    assert response.status_code == 422
    response = client.post("/api/register", json={
        "username": "weakpassworduser2",
        "email": "weakpassworduser2@example.com",
        "password": "abcdefgh"
    })
    assert response.status_code == 422
    response = client.post("/api/register", json={
        "username": "weakpassworduser3",
        "email": "weakpassworduser3@example.com",
        "password": "abc123"
    })
    assert response.status_code == 422

def test_login_success(db):
    user = db.query(User).filter(User.username == "testuser").first()
    assert user
    user.hashed_password = hash_password("Testpassword123")
    user.is_verified = True
    db.add(user)
    db.commit()
    db.refresh(user)  # Ensure the database is up-to-date

    response = client.post("/api/login", json={
        "email": "testuser@example.com",
        "password": "Testpassword123"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"

def test_login_unverified_email(db):
    user = db.query(User).filter(User.username == "testuser").first()
    user.is_verified = False
    db.add(user)
    db.commit()
    db.refresh(user)  # Ensure the database is up-to-date

    response = client.post("/api/login", json={
        "email": "testuser@example.com",
        "password": "Testpassword123"
    })
    assert response.status_code == 403
    assert response.json()["detail"] == "Email not verified"

def test_login_invalid_email(db):
    response = client.post("/api/login", json={
        "email": "invaliduser@example.com",
        "password": "Testpassword123"
    })
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid email or password"

def test_login_invalid_password(db):
    user = db.query(User).filter(User.username == "testuser").first()
    user.is_verified = True
    db.add(user)
    db.commit()
    db.refresh(user)  # Ensure the database is up-to-date

    response = client.post("/api/login", json={
        "email": "testuser@example.com",
        "password": "WrongPassword123"
    })
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid email or password"