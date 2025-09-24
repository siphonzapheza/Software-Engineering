import uuid
import datetime
from sqlalchemy import Column, String, Float, DateTime
from .database import Base

class TenderMetadata(Base):
    __tablename__ = "tender_metadata"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tender_id = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=True)
    buyer = Column(String, index=True, nullable=True)
    province = Column(String, index=True, nullable=True)
    budget_min = Column(Float, nullable=True)
    budget_max = Column(Float, nullable=True)
    deadline = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
