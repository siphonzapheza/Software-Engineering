from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
from datetime import datetime, timedelta
import json

app = FastAPI(
    title="Tender Insight Hub API",
    description="AI-powered tender discovery and analysis platform",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# Pydantic models
class User(BaseModel):
    id: str
    email: str
    firstName: str
    lastName: str
    role: str
    organizationId: str
    createdAt: str
    lastLogin: Optional[str] = None

class Organization(BaseModel):
    id: str
    name: str
    plan: str
    maxUsers: int
    currentUsers: int
    createdAt: str
    subscription: Optional[dict] = None

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    password: str
    firstName: str
    lastName: str
    organizationName: str
    plan: str

class TenderBudget(BaseModel):
    min: Optional[int] = None
    max: Optional[int] = None
    currency: str

class TenderDocument(BaseModel):
    id: str
    name: str
    url: str
    type: str
    size: int

class Tender(BaseModel):
    id: str
    title: str
    description: str
    buyer: str
    province: str
    budget: TenderBudget
    deadline: str
    publishedDate: str
    status: str
    categories: List[str]
    documents: Optional[List[TenderDocument]] = []
    source: str
    ocdsId: Optional[str] = None

class SearchFilters(BaseModel):
    keywords: Optional[str] = None
    provinces: Optional[List[str]] = None
    categories: Optional[List[str]] = None
    budgetMin: Optional[int] = None
    budgetMax: Optional[int] = None
    deadlineFrom: Optional[str] = None
    deadlineTo: Optional[str] = None

# Mock data
mock_tenders = [
    {
        "id": "tender-1",
        "title": "Road Maintenance Services - Gauteng Province",
        "description": "Supply and delivery of road maintenance services including pothole repairs, line marking, and general road upkeep for provincial roads.",
        "buyer": "Gauteng Department of Infrastructure Development",
        "province": "Gauteng",
        "budget": {"min": 5000000, "max": 15000000, "currency": "ZAR"},
        "deadline": "2024-10-15T17:00:00Z",
        "publishedDate": "2024-08-15T10:00:00Z",
        "status": "open",
        "categories": ["Construction", "Infrastructure", "Maintenance"],
        "documents": [
            {"id": "doc-1", "name": "Tender Specification.pdf", "url": "/mock/tender-spec-1.pdf", "type": "pdf", "size": 2048576}
        ],
        "source": "ocds",
        "ocdsId": "ZA-GP-001-2024"
    },
    {
        "id": "tender-2",
        "title": "Security Services for Government Buildings",
        "description": "Provision of comprehensive security services for government buildings in Western Cape, including access control, monitoring, and emergency response.",
        "buyer": "Western Cape Department of Public Works",
        "province": "Western Cape",
        "budget": {"min": 8000000, "max": 12000000, "currency": "ZAR"},
        "deadline": "2024-09-30T17:00:00Z",
        "publishedDate": "2024-08-10T09:00:00Z",
        "status": "open",
        "categories": ["Security", "Services"],
        "documents": [
            {"id": "doc-2", "name": "Security Requirements.pdf", "url": "/mock/security-spec.pdf", "type": "pdf", "size": 1536789}
        ],
        "source": "ocds",
        "ocdsId": "ZA-WC-002-2024"
    },
    {
        "id": "tender-3",
        "title": "ICT Equipment Supply and Installation",
        "description": "Supply, installation and configuration of ICT equipment including computers, servers, networking equipment for municipal offices.",
        "buyer": "eThekwini Municipality",
        "province": "KwaZulu-Natal",
        "budget": {"min": 3000000, "max": 7000000, "currency": "ZAR"},
        "deadline": "2024-11-20T17:00:00Z",
        "publishedDate": "2024-08-20T11:00:00Z",
        "status": "open",
        "categories": ["ICT", "Equipment", "Installation"],
        "source": "ocds",
        "ocdsId": "ZA-KZN-003-2024"
    }
]

# Authentication endpoints
@app.post("/api/auth/login")
async def login(request: LoginRequest):
    # Mock authentication
    mock_user = {
        "id": "1",
        "email": request.email,
        "firstName": "John",
        "lastName": "Doe",
        "role": "admin",
        "organizationId": "org-1",
        "createdAt": datetime.now().isoformat(),
        "lastLogin": datetime.now().isoformat()
    }
    
    mock_org = {
        "id": "org-1",
        "name": "Acme Construction",
        "plan": "basic",
        "maxUsers": 3,
        "currentUsers": 1,
        "createdAt": datetime.now().isoformat(),
        "subscription": {
            "status": "active",
            "expiresAt": (datetime.now() + timedelta(days=30)).isoformat()
        }
    }
    
    return {
        "user": mock_user,
        "organization": mock_org,
        "token": "mock-jwt-token"
    }

@app.post("/api/auth/register")
async def register(request: RegisterRequest):
    # Mock registration
    mock_user = {
        "id": "1",
        "email": request.email,
        "firstName": request.firstName,
        "lastName": request.lastName,
        "role": "admin",
        "organizationId": "org-1",
        "createdAt": datetime.now().isoformat()
    }
    
    max_users = 1 if request.plan == "free" else 3 if request.plan == "basic" else 999
    
    mock_org = {
        "id": "org-1",
        "name": request.organizationName,
        "plan": request.plan,
        "maxUsers": max_users,
        "currentUsers": 1,
        "createdAt": datetime.now().isoformat(),
        "subscription": {
            "status": "active" if request.plan == "free" else "trial",
            "expiresAt": (datetime.now() + timedelta(days=30)).isoformat()
        }
    }
    
    return {
        "user": mock_user,
        "organization": mock_org,
        "token": "mock-jwt-token"
    }

# Tender endpoints
@app.get("/api/tenders", response_model=List[Tender])
async def get_tenders(
    keywords: Optional[str] = None,
    provinces: Optional[str] = None,
    categories: Optional[str] = None,
    budget_min: Optional[int] = None,
    budget_max: Optional[int] = None,
    deadline_from: Optional[str] = None,
    deadline_to: Optional[str] = None
):
    """Get filtered list of tenders"""
    results = mock_tenders.copy()
    
    # Apply filters
    if keywords:
        keywords_lower = keywords.lower()
        results = [t for t in results if 
                  keywords_lower in t["title"].lower() or 
                  keywords_lower in t["description"].lower() or
                  any(keywords_lower in cat.lower() for cat in t["categories"])]
    
    if provinces:
        province_list = provinces.split(",")
        results = [t for t in results if t["province"] in province_list]
    
    if categories:
        category_list = categories.split(",")
        results = [t for t in results if any(cat in category_list for cat in t["categories"])]
    
    if budget_min:
        results = [t for t in results if t["budget"]["max"] and t["budget"]["max"] >= budget_min]
    
    if budget_max:
        results = [t for t in results if t["budget"]["min"] and t["budget"]["min"] <= budget_max]
    
    return results

@app.get("/api/tenders/{tender_id}", response_model=Tender)
async def get_tender(tender_id: str):
    """Get specific tender by ID"""
    tender = next((t for t in mock_tenders if t["id"] == tender_id), None)
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    return tender

@app.post("/api/tenders/{tender_id}/analyze")
async def analyze_tender(tender_id: str):
    """Generate AI analysis for a tender"""
    tender = next((t for t in mock_tenders if t["id"] == tender_id), None)
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    
    # Mock AI analysis
    analysis = {
        "id": f"ai-{tender_id}",
        "tenderId": tender_id,
        "organizationId": "org-1",
        "summary": {
            "objective": f"To procure {tender['title'].lower()}",
            "scope": tender["description"][:200] + "...",
            "deadline": tender["deadline"],
            "eligibilityCriteria": [
                "Valid business registration",
                "Relevant industry experience",
                "Financial capacity requirements",
                "BEE compliance"
            ],
            "keyRequirements": [
                "Technical specifications compliance",
                "Quality assurance program",
                "Project management capability",
                "Local content requirements"
            ],
            "estimatedValue": f"R{tender['budget']['min']:,} - R{tender['budget']['max']:,}"
        },
        "readinessScore": {
            "score": 78,
            "breakdown": [
                {
                    "criteria": "Industry Experience",
                    "matched": True,
                    "importance": "high",
                    "details": "Company has relevant experience in this sector"
                },
                {
                    "criteria": "Geographic Coverage",
                    "matched": True,
                    "importance": "medium",
                    "details": f"Currently operating in {tender['province']}"
                },
                {
                    "criteria": "Financial Capacity",
                    "matched": False,
                    "importance": "high",
                    "details": "May need additional financial backing"
                }
            ],
            "recommendation": "Suitable with some improvements needed",
            "confidence": 0.85
        },
        "processedAt": datetime.now().isoformat(),
        "processingTimeMs": 2500
    }
    
    return analysis

@app.get("/api/dashboard/stats")
async def get_dashboard_stats():
    """Get dashboard statistics"""
    return {
        "totalTenders": len(mock_tenders),
        "savedTenders": 2,
        "interestedTenders": 1,
        "totalValue": sum(t["budget"]["max"] for t in mock_tenders if t["budget"]["max"]),
        "recentTenders": mock_tenders[:3],
        "urgentDeadlines": [t for t in mock_tenders if 
                          (datetime.fromisoformat(t["deadline"].replace('Z', '+00:00')) - datetime.now()).days <= 30]
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
