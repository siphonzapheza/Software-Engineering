import datetime
import uuid
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from .models import TenderMetadata
from .database import mongo_tenders

async def upsert_tender(session: AsyncSession, tender_doc: dict):
    tender_id = tender_doc.get("id") or str(uuid.uuid4())
    title = tender_doc.get("title")
    description = tender_doc.get("description", "")
    buyer = tender_doc.get("buyer")
    province = tender_doc.get("province")
    budget = tender_doc.get("value", {}).get("amount") if isinstance(tender_doc.get("value"), dict) else None
    deadline_str = tender_doc.get("tenderPeriod", {}).get("endDate") if isinstance(tender_doc.get("tenderPeriod"), dict) else None
    deadline = None
    if deadline_str:
        try:
            deadline = datetime.datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
        except:
            pass

    # MongoDB
    await mongo_tenders.replace_one({"_id": tender_id}, {
        "_id": tender_id,
        "title": title,
        "description": description,
        "buyer": buyer,
        "province": province,
        "budget": budget,
        "deadline": deadline.isoformat() if deadline else None,
        "raw": tender_doc
    }, upsert=True)

    # PostgreSQL
    stmt = select(TenderMetadata).where(TenderMetadata.tender_id == tender_id)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        existing.title = title
        existing.buyer = buyer
        existing.province = province
        existing.budget_min = budget
        existing.budget_max = budget
        existing.deadline = deadline
        session.add(existing)
    else:
        new = TenderMetadata(
            tender_id=tender_id,
            title=title,
            buyer=buyer,
            province=province,
            budget_min=budget,
            budget_max=budget,
            deadline=deadline,
        )
        session.add(new)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
    return tender_id
