from fastapi import FastAPI, HTTPException, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy import create_engine, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker, Session
import os

# ===================== Config =====================
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 60 * 24 * 14  # 14 days
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tagz.db")

# ===================== DB setup =====================
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase): pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    bio: Mapped[Optional[str]] = mapped_column(Text, default=None)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, default=None)
    theme_hex: Mapped[Optional[str]] = mapped_column(String(16), default="#00ff88")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    links: Mapped[List["Link"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )

class Link(Base):
    __tablename__ = "links"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(100))
    url: Mapped[str] = mapped_column(Text)
    icon: Mapped[Optional[str]] = mapped_column(String(8), default=None)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    owner: Mapped[User] = relationship(back_populates="links")

Base.metadata.create_all(bind=engine)

# ===================== Auth helpers =====================
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_pw(p: str) -> str:
    return pwd_ctx.hash(p)

def verify_pw(p: str, hashed: str) -> bool:
    return pwd_ctx.verify(p, hashed)

def create_token(data: dict, minutes: int = ACCESS_TOKEN_MINUTES):
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + timedelta(minutes=minutes)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ===================== Schemas =====================
class LinkIn(BaseModel):
    title: str = Field(..., max_length=100)
    url: str
    icon: Optional[str] = None
    order_index: int = 0

class LinkOut(LinkIn):
    id: int
    class Config:
        from_attributes = True

class UserPublic(BaseModel):
    username: str
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    theme_hex: Optional[str] = "#00ff88"
    links: List[LinkOut] = []

class SignupIn(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(..., min_length=6)

class UpdateProfileIn(BaseModel):
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    theme_hex: Optional[str] = None
    links: Optional[List[LinkIn]] = None

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

# ===================== App =====================
app = FastAPI(title="tagz.lol API", version="1.0.0")

# CORS: allow your frontend domain(s)
FRONTENDS = os.getenv("CORS_ORIGINS", "https://tagz.lol,https://www.tagz.lol,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in FRONTENDS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth dependency
from fastapi.security import OAuth2PasswordBearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

def current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.username == username.lower()).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# ===================== Routes =====================
@app.get("/api/health")
def health():
    return {"ok": True, "time": datetime.utcnow().isoformat()}

@app.post("/api/signup", response_model=TokenOut)
def signup(data: SignupIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == data.username.lower()).first():
        raise HTTPException(400, "Username already taken")
    if db.query(User).filter(User.email == data.email.lower()).first():
        raise HTTPException(400, "Email already registered")

    user = User(
        username=data.username.lower(),
        email=data.email.lower(),
        password_hash=hash_pw(data.password),
        bio="",
        avatar_url=None,
    )
    db.add(user)
    db.commit()
    token = create_token({"sub": user.username})
    return {"access_token": token}

@app.post("/api/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # form.username can be username OR email
    q = db.query(User).filter((User.username == form.username.lower()) | (User.email == form.username.lower()))
    user = q.first()
    if not user or not verify_pw(form.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    token = create_token({"sub": user.username})
    return {"access_token": token}

@app.get("/api/me", response_model=UserPublic)
def me(u: User = Depends(current_user)):
    return UserPublic(
        username=u.username,
        bio=u.bio,
        avatar_url=u.avatar_url,
        theme_hex=u.theme_hex,
        links=[LinkOut.model_validate(l) for l in sorted(u.links, key=lambda x: x.order_index)]
    )

@app.put("/api/me", response_model=UserPublic)
def update_me(payload: UpdateProfileIn = Body(...), db: Session = Depends(get_db), u: User = Depends(current_user)):
    if payload.bio is not None: u.bio = payload.bio
    if payload.avatar_url is not None: u.avatar_url = payload.avatar_url
    if payload.theme_hex is not None: u.theme_hex = payload.theme_hex

    if payload.links is not None:
        # replace all links (simplest MVP)
        db.query(Link).filter(Link.user_id == u.id).delete()
        for i, L in enumerate(payload.links):
            db.add(Link(user_id=u.id, title=L.title, url=L.url, icon=L.icon, order_index=L.order_index if L.order_index else i))
    db.commit()
    db.refresh(u)
    return me(u)

@app.get("/api/profile/{username}", response_model=UserPublic)
def public_profile(username: str, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.username == username.lower()).first()
    if not u:
        raise HTTPException(404, "User not found")
    return UserPublic(
        username=u.username,
        bio=u.bio,
        avatar_url=u.avatar_url,
        theme_hex=u.theme_hex,
        links=[LinkOut.model_validate(l) for l in sorted(u.links, key=lambda x: x.order_index)]
    )
