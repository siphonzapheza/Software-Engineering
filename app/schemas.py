import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class FetchRequest(BaseModel):
    tenders: Optional[List[Dict[str, Any]]] = None

class TenderOut(BaseModel):
    tender_id: str
    title: Optional[str]
    buyer: Optional[str]
    province: Optional[str]
    budget_min: Optional[float]
    budget_max: Optional[float]
    deadline: Optional[datetime.datetime]
    excerpt: Optional[str]
