
#  security.py
# Password hashing with bcrypt + JWT token creation/verification


import os
import bcrypt
from datetime import datetime, timedelta
from jose import JWTError, jwt
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY  = os.getenv("JWT_SECRET", "change-this-secret-key-32-chars!!")
ALGORITHM   = "HS256"
EXPIRE_MINS = 30   # token expires in 30 minutes

# ── Password hashing ───
def hash_password(password: str) -> str:
    """Hash password with bcrypt. NEVER store plain passwords."""
    salt   = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode(), salt)
    return hashed.decode()

def verify_password(plain: str, hashed: str) -> bool:
    """Check if plain password matches stored hash"""
    return bcrypt.checkpw(plain.encode(), hashed.encode())

# ── JWT token ──
def create_token(user_id: str) -> str:
    """Create JWT with 30-minute expiry"""
    expire  = datetime.utcnow() + timedelta(minutes=EXPIRE_MINS)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> str | None:
    """Verify JWT and return user_id, or None if invalid/expired"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None

# ── Test ──
if __name__ == "__main__":
    print("Testing security functions...")

    # Password test
    hashed = hash_password("mypassword123")
    print(f"Hash: {hashed[:30]}...")
    print(f"Verify correct: {verify_password('mypassword123', hashed)}")
    print(f"Verify wrong:   {verify_password('wrongpassword', hashed)}")

    # Token test
    token = create_token("user-abc-123")
    print(f"\nToken: {token[:30]}...")
    user_id = verify_token(token)
    print(f"Decoded user_id: {user_id}")
    print(f"Invalid token:   {verify_token('bad.token.here')}")

    print("\nsecurity.py works!")