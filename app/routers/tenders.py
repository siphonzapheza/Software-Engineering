from fastapi import APIRouter, Query
from typing import Optional
from datetime import datetime
from ..database import mongo_tenders

router = APIRouter()

@router.get("/tenders")
async def search_tenders(
    q: Optional[str] = Query(None, description="Keyword search"),
    province: Optional[str] = Query(None, description="Province filter"),
    buyer: Optional[str] = Query(None, description="Buyer filter"),
    min_budget: Optional[float] = Query(None, description="Minimum budget filter"),
    max_budget: Optional[float] = Query(None, description="Maximum budget filter"),
    start_deadline: Optional[datetime] = Query(None, description="Start of submission deadline"),
    end_deadline: Optional[datetime] = Query(None, description="End of submission deadline"),
    limit: int = Query(50, description="Maximum number of results")
):
    """
    Search tenders with multiple filters.
    """
    query = {}

    # Keyword search
    if q:
        query["$text"] = {"$search": q}

    # Province filter
    if province:
        query["province"] = province

    # Buyer filter
    if buyer:
        query["buyer"] = buyer

    # Budget range filter
    if min_budget is not None or max_budget is not None:
        query["budget"] = {}
        if min_budget is not None:
            query["budget"]["$gte"] = min_budget
        if max_budget is not None:
            query["budget"]["$lte"] = max_budget

    # Deadline range filter
    if start_deadline or end_deadline:
        query["deadline"] = {}
        if start_deadline:
            query["deadline"]["$gte"] = start_deadline.isoformat()
        if end_deadline:
            query["deadline"]["$lte"] = end_deadline.isoformat()

    # Fetch results from Mongo
    results = await mongo_tenders.find(query).to_list(length=limit)
    return {"results": results}
