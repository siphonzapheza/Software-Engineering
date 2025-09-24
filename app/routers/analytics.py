from fastapi import APIRouter, Depends, Query
from typing import List, Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
import datetime

from app.database import mongo_db

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

# Helper functions
async def get_mongo_db() -> AsyncIOMotorDatabase:
    return mongo_db

@router.get("/spend-by-buyer")
async def get_spend_by_buyer(
    start_date: Optional[datetime.date] = Query(None, description="Start date for analysis"),
    end_date: Optional[datetime.date] = Query(None, description="End date for analysis"),
    limit: int = Query(10, ge=1, le=100, description="Number of results to return"),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db)
):
    """Returns aggregated government spending data by organizations advertising tenders"""
    # Build match stage for pipeline
    match_stage = {}
    if start_date or end_date:
        date_filter = {}
        if start_date:
            date_filter["$gte"] = datetime.datetime.combine(start_date, datetime.time.min)
        if end_date:
            date_filter["$lte"] = datetime.datetime.combine(end_date, datetime.time.max)
        match_stage["date"] = date_filter
    
    # Build aggregation pipeline
    pipeline = []
    if match_stage:
        pipeline.append({"$match": match_stage})
    
    pipeline.extend([
        {
            "$group": {
                "_id": "$buyer",
                "total_spend": {"$sum": {"$avg": ["$budget_min", "$budget_max"]}},
                "tender_count": {"$sum": 1},
                "avg_budget": {"$avg": {"$avg": ["$budget_min", "$budget_max"]}}
            }
        },
        {"$match": {"_id": {"$ne": None}}},  # Filter out null buyers
        {"$sort": {"total_spend": -1}},
        {"$limit": limit},
        {
            "$project": {
                "buyer": "$_id",
                "total_spend": 1,
                "tender_count": 1,
                "avg_budget": 1,
                "_id": 0
            }
        }
    ])
    
    # Execute aggregation
    result = await db.tenders.aggregate(pipeline).to_list(length=limit)
    
    return result

@router.get("/spend-by-province")
async def get_spend_by_province(
    start_date: Optional[datetime.date] = Query(None, description="Start date for analysis"),
    end_date: Optional[datetime.date] = Query(None, description="End date for analysis"),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db)
):
    """Returns aggregated government spending data by province"""
    # Build match stage for pipeline
    match_stage = {}
    if start_date or end_date:
        date_filter = {}
        if start_date:
            date_filter["$gte"] = datetime.datetime.combine(start_date, datetime.time.min)
        if end_date:
            date_filter["$lte"] = datetime.datetime.combine(end_date, datetime.time.max)
        match_stage["date"] = date_filter
    
    # Build aggregation pipeline
    pipeline = []
    if match_stage:
        pipeline.append({"$match": match_stage})
    
    pipeline.extend([
        {
            "$group": {
                "_id": "$province",
                "total_spend": {"$sum": {"$avg": ["$budget_min", "$budget_max"]}},
                "tender_count": {"$sum": 1}
            }
        },
        {"$match": {"_id": {"$ne": None}}},  # Filter out null provinces
        {"$sort": {"total_spend": -1}},
        {
            "$project": {
                "province": "$_id",
                "total_spend": 1,
                "tender_count": 1,
                "_id": 0
            }
        }
    ])
    
    # Execute aggregation
    result = await db.tenders.aggregate(pipeline).to_list(length=100)
    
    return result

@router.get("/tender-trends")
async def get_tender_trends(
    interval: str = Query("month", description="Aggregation interval: day, week, month, quarter, year"),
    months_back: int = Query(12, ge=1, le=60, description="Number of months to look back"),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db)
):
    """Returns tender count and average budget trends over time"""
    # Calculate start date
    end_date = datetime.datetime.utcnow()
    start_date = end_date - datetime.timedelta(days=30 * months_back)
    
    # Determine date grouping format based on interval
    date_formats = {
        "day": {"$dateToString": {"format": "%Y-%m-%d", "date": "$date"}},
        "week": {"$dateToString": {"format": "%G-W%V", "date": "$date"}},
        "month": {"$dateToString": {"format": "%Y-%m", "date": "$date"}},
        "quarter": {
            "$concat": [
                {"$dateToString": {"format": "%Y-Q", "date": "$date"}},
                {"$toString": {"$ceil": {"$divide": [{"$month": "$date"}, 3]}}}
            ]
        },
        "year": {"$dateToString": {"format": "%Y", "date": "$date"}}
    }
    
    date_group = date_formats.get(interval, date_formats["month"])
    
    # Build aggregation pipeline
    pipeline = [
        {"$match": {"date": {"$gte": start_date, "$lte": end_date}}},
        {
            "$group": {
                "_id": date_group,
                "count": {"$sum": 1},
                "avg_budget": {"$avg": {"$avg": ["$budget_min", "$budget_max"]}}
            }
        },
        {"$sort": {"_id": 1}},
        {
            "$project": {
                "period": "$_id",
                "count": 1,
                "avg_budget": 1,
                "_id": 0
            }
        }
    ]
    
    # Execute aggregation
    result = await db.tenders.aggregate(pipeline).to_list(length=1000)
    
    return result

@router.get("/enriched-releases")
async def get_enriched_releases(
    team_id: Optional[str] = Query(None, description="Filter by team ID for suitability scores"),
    province: Optional[str] = Query(None, description="Filter by province"),
    buyer: Optional[str] = Query(None, description="Filter by buyer"),
    min_budget: Optional[float] = Query(None, description="Filter by minimum budget"),
    max_budget: Optional[float] = Query(None, description="Filter by maximum budget"),
    deadline_from: Optional[datetime.date] = Query(None, description="Filter by deadline from"),
    deadline_to: Optional[datetime.date] = Query(None, description="Filter by deadline to"),
    limit: int = Query(50, ge=1, le=1000, description="Number of results to return"),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db)
):
    """Returns a filtered list of tenders with metadata, AI summary, and suitability score"""
    # Build match query
    match_query = {}
    if province:
        match_query["province"] = province
    if buyer:
        match_query["buyer"] = buyer
    if min_budget is not None:
        match_query["budget_max"] = {"$gte": min_budget}
    if max_budget is not None:
        match_query["budget_min"] = {"$lte": max_budget}
    if deadline_from or deadline_to:
        deadline_query = {}
        if deadline_from:
            deadline_query["$gte"] = datetime.datetime.combine(deadline_from, datetime.time.min)
        if deadline_to:
            deadline_query["$lte"] = datetime.datetime.combine(deadline_to, datetime.time.max)
        match_query["deadline"] = deadline_query
    
    # Get tenders
    cursor = db.tenders.find(match_query).sort("deadline", 1).limit(limit)
    tenders = await cursor.to_list(length=limit)
    
    # If team_id is provided, get readiness scores
    if team_id:
        # Get all readiness scores for this team
        readiness_cursor = db.readiness_scores.find({"team_id": team_id})
        readiness_scores = await readiness_cursor.to_list(length=1000)
        
        # Create a mapping of tender_id to readiness score
        readiness_map = {score["tender_id"]: score for score in readiness_scores}
        
        # Add readiness scores to tenders
        for tender in tenders:
            readiness = readiness_map.get(tender["tender_id"])
            if readiness:
                tender["suitability_score"] = readiness["suitability_score"]
                tender["recommendation"] = readiness["recommendation"]
                tender["checklist"] = readiness["checklist"]
            else:
                tender["suitability_score"] = None
                tender["recommendation"] = None
                tender["checklist"] = None
    
    return tenders