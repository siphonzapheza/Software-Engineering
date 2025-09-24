from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field
import datetime
import uuid

from app.database import AsyncSessionLocal, mongo_db

router = APIRouter(prefix="/api/company-profiles", tags=["Company Profiles"])

# Pydantic models
class CertificationBase(BaseModel):
    name: str
    level: Optional[str] = None
    expiry_date: Optional[datetime.date] = None

class CompanyProfileBase(BaseModel):
    industry_sector: str
    services_provided: List[str]
    certifications: List[CertificationBase] = []
    geographic_coverage: List[str]
    years_experience: int
    contact_email: str
    contact_phone: Optional[str] = None
    website: Optional[str] = None
    bbbee_level: Optional[int] = None
    cidb_grade: Optional[str] = None
    company_size: Optional[str] = None
    company_registration_number: Optional[str] = None

class CompanyProfileCreate(CompanyProfileBase):
    team_id: str

class CompanyProfileUpdate(CompanyProfileBase):
    pass

class CompanyProfileResponse(CompanyProfileBase):
    id: str
    team_id: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        orm_mode = True

# Helper functions
async def get_mongo_db() -> AsyncIOMotorDatabase:
    return mongo_db

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session

# Routes
@router.post("/", response_model=CompanyProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_company_profile(profile: CompanyProfileCreate, db: AsyncIOMotorDatabase = Depends(get_mongo_db)):
    # Check if profile already exists for this team
    existing = await db.company_profiles.find_one({"team_id": profile.team_id})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile already exists for this team"
        )
    
    # Create new profile
    profile_dict = profile.dict()
    profile_dict["id"] = str(uuid.uuid4())
    profile_dict["created_at"] = datetime.datetime.utcnow()
    profile_dict["updated_at"] = profile_dict["created_at"]
    
    await db.company_profiles.insert_one(profile_dict)
    return profile_dict

@router.get("/{team_id}", response_model=CompanyProfileResponse)
async def get_company_profile(team_id: str, db: AsyncIOMotorDatabase = Depends(get_mongo_db)):
    profile = await db.company_profiles.find_one({"team_id": team_id})
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found"
        )
    return profile

@router.put("/{team_id}", response_model=CompanyProfileResponse)
async def update_company_profile(team_id: str, profile: CompanyProfileUpdate, db: AsyncIOMotorDatabase = Depends(get_mongo_db)):
    existing = await db.company_profiles.find_one({"team_id": team_id})
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found"
        )
    
    # Update profile
    profile_dict = profile.dict()
    profile_dict["updated_at"] = datetime.datetime.utcnow()
    
    await db.company_profiles.update_one(
        {"team_id": team_id},
        {"$set": profile_dict}
    )
    
    updated_profile = await db.company_profiles.find_one({"team_id": team_id})
    return updated_profile