
# FastAPI auth routes: register, login, get_current_user


import sys, os, uuid
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import User, get_db
from security import hash_password, verify_password, create_token, verify_token

router = APIRouter(prefix="/auth", tags=["Authentication"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# ── Request models──
class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

# ── Register ───
@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """Create new user account. Returns JWT token."""
    # Check if username already exists
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(status_code=400,
                            detail="Username already exists")

    # Check if email already exists
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=400,
                            detail="Email already registered")

    # Create user
    user = User(
        id=str(uuid.uuid4()),
        username=req.username,
        email=req.email,
        password_hash=hash_password(req.password)
    )
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
        print("REGISTER SUCCESS")
        print("Username:", user.username)
        print("Email:", user.email)
        print("Password Hash:", user.password_hash)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="User creation failed")

    token = create_token(user.id)
    return {"message": "Registration successful", "token": token,
            "user_id": user.id, "username": user.username}

# ── Login ────
@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    print("LOGIN REQUEST")
    print("Username entered:", req.username)

    users = db.query(User).all()

    print("Total users:", len(users))

    for u in users:
        print(f"DB User -> {u.username} | {u.email}" )

    user = db.query(User).filter(User.username == req.username).first()

    if user is None:
        print("User NOT FOUND")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    print("User found:", user.username)
    print("Stored hash:", user.password_hash)

    valid = verify_password(req.password, user.password_hash)

    print("Password verification:", valid)
   

    if not valid:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token(user.id)

    return {
        "message": "Login successful",
        "token": token,
        "user_id": user.id,
        "username": user.username,
    }
# ── Auth dependency ──
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    FastAPI dependency. Add to any route to protect it.
    Usage: current_user: User = Depends(get_current_user)
    """
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401,
                            detail="Invalid or expired token")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# ── Get current user profile ───
@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Returns currently logged in user's profile"""
    return {"user_id": current_user.id,
            "username": current_user.username,
            "email": current_user.email}