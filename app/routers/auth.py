from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, EmailStr, Field
from motor.motor_asyncio import AsyncIOMotorDatabase
import datetime
import uuid
import os
import jwt
from passlib.context import CryptContext

from app.database import mongo_db

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# Security
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

# Pydantic models
class UserBase(BaseModel):
    email: EmailStr
    full_name: str

class UserCreate(UserBase):
    password: str
    team_id: Optional[str] = None

class UserResponse(UserBase):
    id: str
    team_id: str
    is_admin: bool
    created_at: datetime.datetime

class TeamMemberCreate(BaseModel):
    email: EmailStr
    full_name: str
    is_admin: bool = False

class TeamCreate(BaseModel):
    name: str
    admin_email: EmailStr
    admin_name: str
    admin_password: str
    subscription_tier: str = "basic"  # basic, premium, enterprise

class TeamResponse(BaseModel):
    id: str
    name: str
    subscription_tier: str
    created_at: datetime.datetime
    seat_count: int
    seats_used: int

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

# Helper functions
async def get_mongo_db() -> AsyncIOMotorDatabase:
    return mongo_db

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncIOMotorDatabase = Depends(get_mongo_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    
    user = await db.users.find_one({"id": user_id})
    if user is None:
        raise credentials_exception
    
    return user

async def get_current_admin_user(current_user: dict = Depends(get_current_user)):
    if not current_user.get("is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform this action"
        )
    return current_user

async def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Routes
@router.post("/teams", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(team: TeamCreate, db: AsyncIOMotorDatabase = Depends(get_mongo_db)):
    # Check if admin email already exists
    existing_user = await db.users.find_one({"email": team.admin_email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create team
    team_id = str(uuid.uuid4())
    now = datetime.datetime.utcnow()
    
    # Set seat limits based on subscription tier
    seat_limits = {
        "basic": 3,
        "premium": 10,
        "enterprise": 25
    }
    
    team_data = {
        "id": team_id,
        "name": team.name,
        "subscription_tier": team.subscription_tier,
        "seat_count": seat_limits.get(team.subscription_tier, 3),
        "seats_used": 1,  # Admin user
        "created_at": now
    }
    
    await db.teams.insert_one(team_data)
    
    # Create admin user
    user_id = str(uuid.uuid4())
    hashed_password = pwd_context.hash(team.admin_password)
    
    user_data = {
        "id": user_id,
        "email": team.admin_email,
        "full_name": team.admin_name,
        "hashed_password": hashed_password,
        "team_id": team_id,
        "is_admin": True,
        "created_at": now
    }
    
    await db.users.insert_one(user_data)
    
    return team_data

@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncIOMotorDatabase = Depends(get_mongo_db)):
    # Find user by email
    user = await db.users.find_one({"email": form_data.username})
    if not user or not pwd_context.verify(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token_expires = datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = await create_access_token(
        data={"sub": user["id"]},
        expires_delta=access_token_expires
    )
    
    # Prepare user response (exclude password)
    user_response = {
        "id": user["id"],
        "email": user["email"],
        "full_name": user["full_name"],
        "team_id": user["team_id"],
        "is_admin": user["is_admin"],
        "created_at": user["created_at"]
    }
    
    return {"access_token": access_token, "token_type": "bearer", "user": user_response}

@router.post("/team/members", response_model=UserResponse)
async def add_team_member(
    member: TeamMemberCreate,
    current_user: dict = Depends(get_current_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db)
):
    # Check if email already exists
    existing_user = await db.users.find_one({"email": member.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if team has available seats
    team = await db.teams.find_one({"id": current_user["team_id"]})
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    if team["seats_used"] >= team["seat_count"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team has reached maximum seat count"
        )
    
    # Generate temporary password
    temp_password = str(uuid.uuid4())[:8]
    hashed_password = pwd_context.hash(temp_password)
    
    # Create user
    user_id = str(uuid.uuid4())
    now = datetime.datetime.utcnow()
    
    user_data = {
        "id": user_id,
        "email": member.email,
        "full_name": member.full_name,
        "hashed_password": hashed_password,
        "team_id": current_user["team_id"],
        "is_admin": member.is_admin,
        "created_at": now,
        "password_reset_required": True
    }
    
    await db.users.insert_one(user_data)
    
    # Update team seats used
    await db.teams.update_one(
        {"id": current_user["team_id"]},
        {"$inc": {"seats_used": 1}}
    )
    
    # Prepare response (exclude password)
    user_response = {
        "id": user_id,
        "email": member.email,
        "full_name": member.full_name,
        "team_id": current_user["team_id"],
        "is_admin": member.is_admin,
        "created_at": now
    }
    
    # In a real application, you would send an email with the temporary password
    print(f"Temporary password for {member.email}: {temp_password}")
    
    return user_response

@router.get("/team/members", response_model=List[UserResponse])
async def get_team_members(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db)
):
    # Get all users in the team
    cursor = db.users.find({"team_id": current_user["team_id"]})
    team_members = await cursor.to_list(length=100)
    
    # Prepare response (exclude passwords)
    response = []
    for member in team_members:
        response.append({
            "id": member["id"],
            "email": member["email"],
            "full_name": member["full_name"],
            "team_id": member["team_id"],
            "is_admin": member["is_admin"],
            "created_at": member["created_at"]
        })
    
    return response

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    # Prepare response (exclude password)
    user_response = {
        "id": current_user["id"],
        "email": current_user["email"],
        "full_name": current_user["full_name"],
        "team_id": current_user["team_id"],
        "is_admin": current_user["is_admin"],
        "created_at": current_user["created_at"]
    }
    
    return user_response