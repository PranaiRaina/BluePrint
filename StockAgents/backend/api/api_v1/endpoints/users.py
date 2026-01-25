from fastapi import APIRouter, Depends, HTTPException, Body
from typing import Any, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from api import deps
from core.security import encrypt_data, decrypt_data
from models.user import User, RiskTolerance
from db.session import engine
from sqlalchemy.future import select

# Pydantic Schemas
class UserSettingsUpdate(BaseModel):
    alpha_vantage_key: Optional[str] = None
    wolfram_app_id: Optional[str] = None
    risk_tolerance: Optional[str] = None # 'low', 'medium', 'high'

class UserResponse(BaseModel):
    email: str
    risk_tolerance: str
    has_alpha_vantage_key: bool
    has_wolfram_key: bool

router = APIRouter()

# Mock DB interaction for now since we don't have full User CRUD/Auth wired to DB yet
# We will use the "admin" user for this Sprint
async def get_or_create_admin_user(session: Session) -> User:
    result = await session.execute(select(User).where(User.email == "admin@example.com"))
    user = result.scalars().first()
    if not user:
        user = User(
            email="admin@example.com", 
            hashed_password="mock_hash",
            risk_tolerance=RiskTolerance.MEDIUM.value
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user

@router.get("/me", response_model=UserResponse)
async def read_user_me(
    current_user: Any = Depends(deps.get_current_user), # Still using mock token dependency
) -> Any:
    """
    Get current user profile (with masked keys).
    """
    # Quick hack: Fetch the 'admin' user from DB directly since deps.get_current_user is mock
    async with engine.connect() as conn:
         # We need a session, so let's use the one from deps if we had it, or use run_sync
         # Ideally, we should inject db session into endpoint. 
         # For simplicity in this sprint, we open a new session context here or assume single user
         pass
    
    # Better approach: Dependency Injection for DB
    from db.session import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        user = await get_or_create_admin_user(session)
        
        return {
            "email": user.email,
            "risk_tolerance": user.risk_tolerance,
            "has_alpha_vantage_key": bool(user.alpha_vantage_key),
            "has_wolfram_key": bool(user.wolfram_app_id)
        }

@router.put("/me/settings", response_model=UserResponse)
async def update_user_settings(
    settings: UserSettingsUpdate,
    current_user: Any = Depends(deps.get_current_user),
) -> Any:
    """
    Update API keys and risk tolerance.
    """
    from db.session import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        user = await get_or_create_admin_user(session)
        
        if settings.alpha_vantage_key:
            user.alpha_vantage_key = encrypt_data(settings.alpha_vantage_key)
        if settings.wolfram_app_id:
            user.wolfram_app_id = encrypt_data(settings.wolfram_app_id)
        if settings.risk_tolerance:
             user.risk_tolerance = settings.risk_tolerance
             
        session.add(user)
        await session.commit()
        await session.refresh(user)

        return {
            "email": user.email,
            "risk_tolerance": user.risk_tolerance,
            "has_alpha_vantage_key": bool(user.alpha_vantage_key),
            "has_wolfram_key": bool(user.wolfram_app_id)
        }
