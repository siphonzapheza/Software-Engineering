from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorDatabase
import datetime
import uuid

from app.database import mongo_db

router = APIRouter(prefix="/api/readiness", tags=["Readiness Scoring"])

# Pydantic models
class ReadinessCheckRequest(BaseModel):
    tender_id: str
    team_id: str

class ChecklistItem(BaseModel):
    criterion: str
    matched: bool
    importance: int = 1  # 1-5 scale of importance

class ReadinessResponse(BaseModel):
    id: str
    tender_id: str
    team_id: str
    suitability_score: int  # 0-100
    checklist: List[ChecklistItem]
    recommendation: str
    created_at: datetime.datetime

# Helper functions
async def get_mongo_db() -> AsyncIOMotorDatabase:
    return mongo_db

async def calculate_suitability_score(
    tender_data: Dict[str, Any],
    company_profile: Dict[str, Any]
) -> tuple[int, List[ChecklistItem], str]:
    """Calculate suitability score based on tender requirements and company profile"""
    checklist = []
    total_points = 0
    max_points = 0
    
    # Check industry sector match
    if "industry_sector" in tender_data and "industry_sector" in company_profile:
        importance = 5
        max_points += importance
        matched = tender_data["industry_sector"].lower() == company_profile["industry_sector"].lower()
        if matched:
            total_points += importance
        checklist.append(ChecklistItem(
            criterion=f"Industry sector match: {tender_data['industry_sector']}",
            matched=matched,
            importance=importance
        ))
    
    # Check geographic coverage
    if "province" in tender_data and "geographic_coverage" in company_profile:
        importance = 4
        max_points += importance
        matched = tender_data["province"] in company_profile["geographic_coverage"]
        if matched:
            total_points += importance
        checklist.append(ChecklistItem(
            criterion=f"Operates in province: {tender_data['province']}",
            matched=matched,
            importance=importance
        ))
    
    # Check CIDB requirements
    if "cidb_required" in tender_data and tender_data["cidb_required"] and "cidb_grade" in company_profile:
        importance = 5
        max_points += importance
        required_grade = tender_data.get("cidb_grade", "")
        company_grade = company_profile.get("cidb_grade", "")
        
        # Convert grades to numeric for comparison (e.g., "Grade 7" -> 7)
        try:
            required_grade_num = int(required_grade.split()[-1]) if required_grade else 0
            company_grade_num = int(company_grade.split()[-1]) if company_grade else 0
            matched = company_grade_num >= required_grade_num
            if matched:
                total_points += importance
        except (ValueError, IndexError):
            matched = False
            
        checklist.append(ChecklistItem(
            criterion=f"Has required CIDB grade: {required_grade}",
            matched=matched,
            importance=importance
        ))
    
    # Check BBBEE requirements
    if "bbbee_level_required" in tender_data and "bbbee_level" in company_profile:
        importance = 4
        max_points += importance
        required_level = tender_data.get("bbbee_level_required", 0)
        company_level = company_profile.get("bbbee_level", 0)
        matched = company_level <= required_level  # Lower is better in BBBEE
        if matched:
            total_points += importance
        checklist.append(ChecklistItem(
            criterion=f"Meets BBBEE level requirement: {required_level}",
            matched=matched,
            importance=importance
        ))
    
    # Check years of experience
    if "min_years_experience" in tender_data and "years_experience" in company_profile:
        importance = 3
        max_points += importance
        required_years = tender_data.get("min_years_experience", 0)
        company_years = company_profile.get("years_experience", 0)
        matched = company_years >= required_years
        if matched:
            total_points += importance
        checklist.append(ChecklistItem(
            criterion=f"Has required experience: {required_years} years",
            matched=matched,
            importance=importance
        ))
    
    # Calculate final score (0-100)
    score = int((total_points / max_points * 100) if max_points > 0 else 50)
    
    # Generate recommendation
    if score >= 80:
        recommendation = "Highly suitable - strong match for requirements"
    elif score >= 60:
        recommendation = "Suitable - good match with some gaps"
    elif score >= 40:
        recommendation = "Moderately suitable - significant gaps exist"
    else:
        recommendation = "Not suitable - major requirements not met"
    
    return score, checklist, recommendation

# Routes
@router.post("/check", response_model=ReadinessResponse)
async def check_readiness(
    request: ReadinessCheckRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db)
):
    # Get company profile
    company_profile = await db.company_profiles.find_one({"team_id": request.team_id})
    if not company_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found"
        )
    
    # Get tender data
    tender = await db.tenders.find_one({"tender_id": request.tender_id})
    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tender not found"
        )
    
    # Calculate suitability score
    score, checklist, recommendation = await calculate_suitability_score(tender, company_profile)
    
    # Create readiness record
    readiness_id = str(uuid.uuid4())
    readiness_data = {
        "id": readiness_id,
        "tender_id": request.tender_id,
        "team_id": request.team_id,
        "suitability_score": score,
        "checklist": [item.dict() for item in checklist],
        "recommendation": recommendation,
        "created_at": datetime.datetime.utcnow()
    }
    
    await db.readiness_scores.insert_one(readiness_data)
    
    return ReadinessResponse(**readiness_data)

@router.get("/{tender_id}/{team_id}", response_model=ReadinessResponse)
async def get_readiness_score(
    tender_id: str,
    team_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db)
):
    # Get existing readiness score
    readiness = await db.readiness_scores.find_one({
        "tender_id": tender_id,
        "team_id": team_id
    })
    
    if not readiness:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Readiness score not found"
        )
    
    return ReadinessResponse(**readiness)