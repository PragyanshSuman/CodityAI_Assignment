from fastapi import APIRouter, Depends, HTTPException, status
import asyncpg
import uuid

from app.database import get_db
from app.dependencies import hash_password, verify_password, create_access_token, create_refresh_token, decode_token, get_current_user
from app.models.auth import UserRegister, UserLogin, TokenResponse, RefreshRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(body: UserRegister, db: asyncpg.Connection = Depends(get_db)):
    existing = await db.fetchrow("SELECT id FROM users WHERE email = $1", body.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = await db.fetchrow(
        """INSERT INTO users (email, password_hash, full_name)
           VALUES ($1, $2, $3)
           RETURNING id, email, full_name, is_active, created_at""",
        body.email, hash_password(body.password), body.full_name,
    )
    return dict(user)


@router.post("/login", response_model=TokenResponse)
async def login(body: UserLogin, db: asyncpg.Connection = Depends(get_db)):
    user = await db.fetchrow(
        "SELECT id, email, password_hash, is_active FROM users WHERE email = $1", body.email
    )
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="Account deactivated")

    token_data = {"sub": str(user["id"]), "email": user["email"]}
    return {
        "access_token": create_access_token(token_data),
        "refresh_token": create_refresh_token(token_data),
        "token_type": "bearer",
        "expires_in": 3600,
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, db: asyncpg.Connection = Depends(get_db)):
    token_data = decode_token(body.refresh_token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = await db.fetchrow(
        "SELECT id, email, is_active FROM users WHERE id = $1", token_data.user_id
    )
    if not user or not user["is_active"]:
        raise HTTPException(status_code=401, detail="User not found")

    token_payload = {"sub": str(user["id"]), "email": user["email"]}
    return {
        "access_token": create_access_token(token_payload),
        "refresh_token": create_refresh_token(token_payload),
        "token_type": "bearer",
        "expires_in": 3600,
    }


@router.get("/me", response_model=UserResponse)
async def me(current_user: dict = Depends(get_current_user)):
    return current_user
