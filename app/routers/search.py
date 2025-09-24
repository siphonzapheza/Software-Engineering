from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorDatabase
import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, func
from sqlalchemy.sql import text

from app.database import AsyncSessionLocal, mongo_db
from app.models import TenderMetadata

router = APIRouter(prefix="/api/search", tags=["Search"])

# Pydantic models
class SearchRequest(BaseModel):
    keywords: str
    province: Optional[str] = None
    buyer: Optional[str] = None
    min_budget: Optional[float] = None
    max_budget: Optional[float] = None
    deadline_from: Optional[datetime.datetime] = None
    deadline_to: Optional[datetime.datetime] = None

class SearchResult(BaseModel):
    tender_id: str
    title: str
    buyer: Optional[str] = None
    province: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    deadline: Optional[datetime.datetime] = None
    excerpt: Optional[str] = None
    relevance_score: float

# Helper functions
async def get_mongo_db() -> AsyncIOMotorDatabase:
    return mongo_db

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session

async def search_tenders(
    keywords: str,
    province: Optional[str] = None,
    buyer: Optional[str] = None,
    min_budget: Optional[float] = None,
    max_budget: Optional[float] = None,
    deadline_from: Optional[datetime.datetime] = None,
    deadline_to: Optional[datetime.datetime] = None,
    db: AsyncSession = None,
    mongo_db: AsyncIOMotorDatabase = None
) -> List[Dict[str, Any]]:
    """Search tenders based on keywords and filters"""
    # Split keywords into individual terms
    search_terms = keywords.lower().split()
    
    # Build SQL query for initial search
    query = select(TenderMetadata)
    
    # Apply filters if provided
    filters = []
    if province:
        filters.append(TenderMetadata.province == province)
    if buyer:
        filters.append(TenderMetadata.buyer == buyer)
    if min_budget is not None:
        filters.append(TenderMetadata.budget_max >= min_budget)
    if max_budget is not None:
        filters.append(TenderMetadata.budget_min <= max_budget)
    if deadline_from:
        filters.append(TenderMetadata.deadline >= deadline_from)
    if deadline_to:
        filters.append(TenderMetadata.deadline <= deadline_to)
    
    if filters:
        query = query.where(and_(*filters))
    
    # Execute query
    result = await db.execute(query)
    tenders = result.scalars().all()
    
    # Get full tender details from MongoDB
    tender_ids = [tender.tender_id for tender in tenders]
    mongo_tenders = await mongo_db.tenders.find({"tender_id": {"$in": tender_ids}}).to_list(length=1000)
    
    # Create a mapping of tender_id to MongoDB document
    mongo_tenders_map = {tender["tender_id"]: tender for tender in mongo_tenders}
    
    # Calculate relevance scores based on keyword matches
    results = []
    for tender in tenders:
        mongo_tender = mongo_tenders_map.get(tender.tender_id, {})
        description = mongo_tender.get("description", "").lower()
        
        # Calculate simple relevance score based on keyword occurrences
        relevance_score = 0
        for term in search_terms:
            if term in description:
                relevance_score += 1
        
        # Normalize score
        if search_terms:
            relevance_score = relevance_score / len(search_terms)
        
        # Create result object
        result = {
            "tender_id": tender.tender_id,
            "title": tender.title,
            "buyer": tender.buyer,
            "province": tender.province,
            "budget_min": tender.budget_min,
            "budget_max": tender.budget_max,
            "deadline": tender.deadline,
            "excerpt": description[:200] + "..." if len(description) > 200 else description,
            "relevance_score": relevance_score
        }
        
        results.append(result)
    
    # Sort by relevance score
    results.sort(key=lambda x: x["relevance_score"], reverse=True)
    
    return results

# Routes
@router.post("/tenders", response_model=List[SearchResult])
async def search_tenders_endpoint(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo_db)
):
    results = await search_tenders(
        keywords=request.keywords,
        province=request.province,
        buyer=request.buyer,
        min_budget=request.min_budget,
        max_budget=request.max_budget,
        deadline_from=request.deadline_from,
        deadline_to=request.deadline_to,
        db=db,
        mongo_db=mongo_db
    )
    
    return results

@router.get("/filters")
async def get_filter_options(db: AsyncSession = Depends(get_db)):
    """Get available filter options for provinces and buyers"""
    # Get distinct provinces
    provinces_query = select(TenderMetadata.province).distinct()
    provinces_result = await db.execute(provinces_query)
    provinces = [p for p in provinces_result.scalars().all() if p]
    
    # Get distinct buyers
    buyers_query = select(TenderMetadata.buyer).distinct()
    buyers_result = await db.execute(buyers_query)
    buyers = [b for b in buyers_result.scalars().all() if b]
    
    # Get min/max budget ranges
    budget_min_query = select(func.min(TenderMetadata.budget_min))
    budget_min_result = await db.execute(budget_min_query)
    min_budget = budget_min_result.scalar()
    
    budget_max_query = select(func.max(TenderMetadata.budget_max))
    budget_max_result = await db.execute(budget_max_query)
    max_budget = budget_max_result.scalar()
    
    # Get earliest and latest deadlines
    deadline_min_query = select(func.min(TenderMetadata.deadline))
    deadline_min_result = await db.execute(deadline_min_query)
    earliest_deadline = deadline_min_result.scalar()
    
    deadline_max_query = select(func.max(TenderMetadata.deadline))
    deadline_max_result = await db.execute(deadline_max_query)
    latest_deadline = deadline_max_result.scalar()
    
    return {
        "provinces": provinces,
        "buyers": buyers,
        "budget_range": {
            "min": min_budget,
            "max": max_budget
        },
        "deadline_range": {
            "earliest": earliest_deadline,
            "latest": latest_deadline
        }
    }