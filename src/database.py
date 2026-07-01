import uuid
from datetime import datetime, timezone
# FIX 1: Import declarative_base from sqlalchemy.orm (not ext.declarative)
#         ext.declarative is DEPRECATED in SQLAlchemy 2.0+
#         Your code used the old location which gives a DeprecationWarning
from sqlalchemy import (
    create_engine, Column, String,
    DateTime, Boolean, Index
)
from sqlalchemy.orm import declarative_base, sessionmaker

# ── 1. SCHEMA INITIALIZATION ──────────────────────────────────
Base = declarative_base()

class User(Base):
    """
    User Table Model
    Represents the 'users' table in SQLite using SQLAlchemy ORM.

    Columns:
        id            → UUID string primary key (auto-generated)
        username      → Unique login name
        email         → Unique email address
        password_hash → bcrypt hash (never store plain password)
        is_active     → Account enabled/disabled flag
        created_at    → Auto timestamp when account was created
    """
    __tablename__ = "users"

    id            = Column(String,   primary_key=True,
                           default=lambda: str(uuid.uuid4()))
    username      = Column(String,   unique=True,  nullable=False)
    email         = Column(String,   unique=True,  nullable=False)
    password_hash = Column(String,   nullable=False)
    is_active     = Column(Boolean,  default=True)

    # FIX 2: datetime.utcnow is DEPRECATED in Python 3.12+
    #         Use datetime.now(timezone.utc) instead
    #         Must wrap in lambda so it's called at INSERT time
    #         (not at class definition time)
    created_at    = Column(DateTime,
                           default=lambda: datetime.now(timezone.utc))

    # IMPROVEMENT 1: Indexes on username and email
    # Without these, every login does a full table scan
    # With index: O(log n) lookup instead of O(n)
    __table_args__ = (
        Index("ix_users_username", "username"),
        Index("ix_users_email",    "email"),
    )

    # IMPROVEMENT 2: __repr__ for debugging
    # Without this: <User object at 0x7f3a2b1c4d50> (useless)
    # With this:    User(id=abc, username=keerthana, active=True)
    def __repr__(self):
        return (
            f"User("
            f"id={self.id[:8]}..., "
            f"username={self.username}, "
            f"active={self.is_active})"
        )

    # IMPROVEMENT 3: Helper method to check if user is valid
    def is_valid(self):
        """Returns True if user account is active"""
        return self.is_active is True


# ── 2. DATABASE CONNECTION ────────────────────────────────────
# SQLite file stored in project root
# check_same_thread=False needed for FastAPI async requests
DB_URL = "sqlite:///./rag_users.db"

engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False},
    # FIX 3: echo=False in production
    # Set echo=True only for debugging SQL queries
    echo=False
)

# Create all tables defined above (if they don't exist yet)
# Safe to call multiple times — skips existing tables
Base.metadata.create_all(bind=engine)

# Session factory
# autocommit=False → must call db.commit() manually after changes
# autoflush=False  → don't auto-send SQL before every query
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


# ── 3. FASTAPI DEPENDENCY ─────────────────────────────────────
def get_db():
    """
    FastAPI dependency — provides a database session to routes.

    Usage in FastAPI endpoint:
        @router.post("/register")
        def register(db: Session = Depends(get_db)):
            user = db.query(User).filter(...).first()
            ...

    The 'finally' block ensures db.close() is ALWAYS called
    even if the route raises an exception.
    This prevents connection leaks.
    """
    db = SessionLocal()
    try:
        yield db        # ← route function runs here
    finally:
        db.close()      # ← always runs after route finishes


# ── 4. CONSOLIDATED TEST BLOCK ────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("DATABASE SYSTEM CHECK")
    print("=" * 50)

    db = SessionLocal()
    try:
        # ── Step 1: Verify connection + count users ────────────
        count = db.query(User).count()
        print(f"\n   Database connected: rag_users.db")
        print(f"    Total users in DB: {count}")

        # ── Step 2: Check indexes exist ───────────────────────
        from sqlalchemy import inspect
        inspector = inspect(engine)
        indexes   = inspector.get_indexes("users")
        idx_names = [idx["name"] for idx in indexes]
        print(f"    Indexes: {idx_names}")

        # ── Step 3: Create test user safely ───────────────────
        test_username = "keerthana_test"
        existing = db.query(User).filter(
            User.username == test_username
        ).first()

        if not existing:
            print(f"\n  [→] Creating test user '{test_username}'...")
            try:
                from security import hash_password
                new_user = User(
                    username=test_username,
                    email=f"{test_username}@example.com",
                    password_hash=hash_password("admin123")
                )
                db.add(new_user)
                db.commit()
                db.refresh(new_user)  # reload to get auto-generated id
                print(f"   Test user created!")
                print(f"    User: {new_user}")  # uses __repr__
                print(f"    Created at: {new_user.created_at}")
                print(f"    Is valid: {new_user.is_valid()}")
            except ImportError:
                print("   security.py not found. "
                      "Skipping user creation.")
            except Exception as e:
                db.rollback()  # ← always rollback on error!
                print(f"    User creation failed: {e}")
        else:
            print(f"\n    User '{test_username}' already exists.")
            print(f"   User repr: {existing}")
            print(f"    Created at: {existing.created_at}")

        # ── Step 4: Test query performance ───────────────────
        print("\n  Testing query by username...")
        found = db.query(User).filter(
            User.username == test_username
        ).first()
        if found:
            print(f"   Query OK: {found}")
        else:
            print(f"    User not found (create it first)")

    except Exception as e:
        print(f"\n  [✗] System check failed: {e}")
        db.rollback()
    finally:
        db.close()

    print("\n" + "-" * 50)
    print("database.py check complete.")
    print("-" * 50)
