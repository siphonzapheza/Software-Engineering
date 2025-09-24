from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorDatabase
import datetime
import uuid

from app.database import mongo_db

router = APIRouter(prefix="/api/workspace", tags=["Workspace"])

# Pydantic models
class TenderNote(BaseModel):
    content: str
    created_by: str
    created_at: datetime.datetime = None

class TenderTask(BaseModel):
    description: str
    assigned_to: Optional[str] = None
    due_date: Optional[datetime.date] = None
    status: str = "pending"  # pending, in_progress, completed
    created_by: str
    created_at: datetime.datetime = None

class WorkspaceItemCreate(BaseModel):
    tender_id: str
    team_id: str
    status: str = "pending"  # pending, interested, not_eligible, submitted, won, lost
    notes: Optional[List[TenderNote]] = None
    tasks: Optional[List[TenderTask]] = None

class WorkspaceItemUpdate(BaseModel):
    status: Optional[str] = None
    updated_by: str

class WorkspaceItemResponse(BaseModel):
    id: str
    tender_id: str
    team_id: str
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    updated_by: Optional[str] = None
    notes: List[TenderNote] = []
    tasks: List[TenderTask] = []
    # These fields will be populated from the tender collection
    tender_title: Optional[str] = None
    tender_deadline: Optional[datetime.datetime] = None
    tender_summary: Optional[str] = None
    match_score: Optional[int] = None

# Helper functions
async def get_mongo_db() -> AsyncIOMotorDatabase:
    return mongo_db

# Routes
@router.post("/", response_model=WorkspaceItemResponse, status_code=status.HTTP_201_CREATED)
async def add_tender_to_workspace(
    item: WorkspaceItemCreate,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db)
):
    # Check if tender exists
    tender = await db.tenders.find_one({"tender_id": item.tender_id})
    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tender not found"
        )
    
    # Check if already in workspace
    existing = await db.workspace.find_one({
        "tender_id": item.tender_id,
        "team_id": item.team_id
    })
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tender already in workspace"
        )
    
    # Create workspace item
    now = datetime.datetime.utcnow()
    workspace_id = str(uuid.uuid4())
    
    # Process notes and tasks
    notes = []
    if item.notes:
        for note in item.notes:
            note_dict = note.dict()
            note_dict["created_at"] = now
            notes.append(note_dict)
    
    tasks = []
    if item.tasks:
        for task in item.tasks:
            task_dict = task.dict()
            task_dict["created_at"] = now
            tasks.append(task_dict)
    
    workspace_data = {
        "id": workspace_id,
        "tender_id": item.tender_id,
        "team_id": item.team_id,
        "status": item.status,
        "created_at": now,
        "updated_at": now,
        "notes": notes,
        "tasks": tasks
    }
    
    await db.workspace.insert_one(workspace_data)
    
    # Get readiness score if available
    readiness = await db.readiness_scores.find_one({
        "tender_id": item.tender_id,
        "team_id": item.team_id
    })
    
    # Combine with tender data for response
    response_data = workspace_data.copy()
    response_data["tender_title"] = tender.get("title")
    response_data["tender_deadline"] = tender.get("deadline")
    response_data["tender_summary"] = tender.get("summary")
    response_data["match_score"] = readiness.get("suitability_score") if readiness else None
    
    return WorkspaceItemResponse(**response_data)

@router.get("/team/{team_id}", response_model=List[WorkspaceItemResponse])
async def get_team_workspace(
    team_id: str,
    status: Optional[str] = Query(None, description="Filter by status"),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db)
):
    # Build query
    query = {"team_id": team_id}
    if status:
        query["status"] = status
    
    # Get workspace items
    cursor = db.workspace.find(query).sort("created_at", -1)
    workspace_items = await cursor.to_list(length=100)
    
    # Enrich with tender data and readiness scores
    response_items = []
    for item in workspace_items:
        tender = await db.tenders.find_one({"tender_id": item["tender_id"]})
        readiness = await db.readiness_scores.find_one({
            "tender_id": item["tender_id"],
            "team_id": team_id
        })
        
        item["tender_title"] = tender.get("title") if tender else None
        item["tender_deadline"] = tender.get("deadline") if tender else None
        item["tender_summary"] = tender.get("summary") if tender else None
        item["match_score"] = readiness.get("suitability_score") if readiness else None
        
        response_items.append(WorkspaceItemResponse(**item))
    
    # Sort by match score if available
    response_items.sort(key=lambda x: (x.match_score or 0), reverse=True)
    
    return response_items

@router.put("/{workspace_id}", response_model=WorkspaceItemResponse)
async def update_workspace_item(
    workspace_id: str,
    update: WorkspaceItemUpdate,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db)
):
    # Check if workspace item exists
    existing = await db.workspace.find_one({"id": workspace_id})
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace item not found"
        )
    
    # Update fields
    update_data = {"updated_at": datetime.datetime.utcnow(), "updated_by": update.updated_by}
    if update.status:
        update_data["status"] = update.status
    
    await db.workspace.update_one(
        {"id": workspace_id},
        {"$set": update_data}
    )
    
    # Get updated item
    updated_item = await db.workspace.find_one({"id": workspace_id})
    
    # Enrich with tender data and readiness score
    tender = await db.tenders.find_one({"tender_id": updated_item["tender_id"]})
    readiness = await db.readiness_scores.find_one({
        "tender_id": updated_item["tender_id"],
        "team_id": updated_item["team_id"]
    })
    
    updated_item["tender_title"] = tender.get("title") if tender else None
    updated_item["tender_deadline"] = tender.get("deadline") if tender else None
    updated_item["tender_summary"] = tender.get("summary") if tender else None
    updated_item["match_score"] = readiness.get("suitability_score") if readiness else None
    
    return WorkspaceItemResponse(**updated_item)

@router.post("/{workspace_id}/notes", response_model=WorkspaceItemResponse)
async def add_note_to_workspace_item(
    workspace_id: str,
    note: TenderNote,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db)
):
    # Check if workspace item exists
    existing = await db.workspace.find_one({"id": workspace_id})
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace item not found"
        )
    
    # Add note
    note_dict = note.dict()
    note_dict["created_at"] = datetime.datetime.utcnow()
    
    await db.workspace.update_one(
        {"id": workspace_id},
        {
            "$push": {"notes": note_dict},
            "$set": {"updated_at": datetime.datetime.utcnow()}
        }
    )
    
    # Get updated item
    updated_item = await db.workspace.find_one({"id": workspace_id})
    
    # Enrich with tender data and readiness score
    tender = await db.tenders.find_one({"tender_id": updated_item["tender_id"]})
    readiness = await db.readiness_scores.find_one({
        "tender_id": updated_item["tender_id"],
        "team_id": updated_item["team_id"]
    })
    
    updated_item["tender_title"] = tender.get("title") if tender else None
    updated_item["tender_deadline"] = tender.get("deadline") if tender else None
    updated_item["tender_summary"] = tender.get("summary") if tender else None
    updated_item["match_score"] = readiness.get("suitability_score") if readiness else None
    
    return WorkspaceItemResponse(**updated_item)

@router.post("/{workspace_id}/tasks", response_model=WorkspaceItemResponse)
async def add_task_to_workspace_item(
    workspace_id: str,
    task: TenderTask,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db)
):
    # Check if workspace item exists
    existing = await db.workspace.find_one({"id": workspace_id})
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace item not found"
        )
    
    # Add task
    task_dict = task.dict()
    task_dict["created_at"] = datetime.datetime.utcnow()
    
    await db.workspace.update_one(
        {"id": workspace_id},
        {
            "$push": {"tasks": task_dict},
            "$set": {"updated_at": datetime.datetime.utcnow()}
        }
    )
    
    # Get updated item
    updated_item = await db.workspace.find_one({"id": workspace_id})
    
    # Enrich with tender data and readiness score
    tender = await db.tenders.find_one({"tender_id": updated_item["tender_id"]})
    readiness = await db.readiness_scores.find_one({
        "tender_id": updated_item["tender_id"],
        "team_id": updated_item["team_id"]
    })
    
    updated_item["tender_title"] = tender.get("title") if tender else None
    updated_item["tender_deadline"] = tender.get("deadline") if tender else None
    updated_item["tender_summary"] = tender.get("summary") if tender else None
    updated_item["match_score"] = readiness.get("suitability_score") if readiness else None
    
    return WorkspaceItemResponse(**updated_item)