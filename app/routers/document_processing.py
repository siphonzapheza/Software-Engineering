from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends, status
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
import uuid
import datetime
import io
import os
import tempfile
import shutil
import PyPDF2
import docx
import zipfile
import httpx

from app.database import mongo_db

router = APIRouter(prefix="/api", tags=["Document Processing"])

# Helper functions
async def get_mongo_db() -> AsyncIOMotorDatabase:
    return mongo_db

async def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from PDF file"""
    text = ""
    try:
        with open(file_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            for page_num in range(len(pdf_reader.pages)):
                text += pdf_reader.pages[page_num].extract_text() + "\n"
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
    return text

async def extract_text_from_docx(file_path: str) -> str:
    """Extract text from DOCX file"""
    text = ""
    try:
        doc = docx.Document(file_path)
        for para in doc.paragraphs:
            text += para.text + "\n"
    except Exception as e:
        print(f"Error extracting text from DOCX: {e}")
    return text

async def extract_text_from_zip(file_path: str) -> str:
    """Extract text from all documents in ZIP file"""
    text = ""
    temp_dir = tempfile.mkdtemp()
    try:
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
            
        # Process all files in the extracted directory
        for root, _, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                if file.lower().endswith('.pdf'):
                    text += await extract_text_from_pdf(file_path) + "\n\n"
                elif file.lower().endswith('.docx'):
                    text += await extract_text_from_docx(file_path) + "\n\n"
    except Exception as e:
        print(f"Error extracting text from ZIP: {e}")
    finally:
        shutil.rmtree(temp_dir)
    return text

async def summarize_text(text: str, max_length: int = 120) -> str:
    """Summarize text using an AI model"""
    # For now, we'll use a simple extractive summarization
    # In a production environment, you would use a proper NLP model or LLM API
    
    # Simple extractive summarization
    sentences = text.split('.')
    if len(sentences) <= 3:
        return text
    
    # Take first 3 sentences as a simple summary
    summary = '. '.join(sentences[:3]) + '.'
    
    # In production, replace with actual AI summarization
    # Example with HuggingFace API (commented out):
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api-inference.huggingface.co/models/facebook/bart-large-cnn",
            headers={"Authorization": f"Bearer {os.getenv('HUGGINGFACE_API_KEY')}"},
            json={"inputs": text, "parameters": {"max_length": max_length}}
        )
        if response.status_code == 200:
            summary = response.json()[0]["summary_text"]
        else:
            summary = "Error generating summary."
    """
    
    return summary

# Routes
@router.post("/summary/extract", response_model=Dict[str, Any])
async def extract_document_summary(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db)
):
    # Create a temporary file to store the uploaded file
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    try:
        # Write uploaded file to temporary file
        shutil.copyfileobj(file.file, temp_file)
        temp_file.close()
        
        # Extract text based on file type
        file_extension = os.path.splitext(file.filename)[1].lower()
        text = ""
        
        if file_extension == ".pdf":
            text = await extract_text_from_pdf(temp_file.name)
        elif file_extension == ".docx":
            text = await extract_text_from_docx(temp_file.name)
        elif file_extension == ".zip":
            text = await extract_text_from_zip(temp_file.name)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file format. Please upload PDF, DOCX, or ZIP files."
            )
        
        # Generate summary
        summary = await summarize_text(text)
        
        # Store in database
        document_id = str(uuid.uuid4())
        document_data = {
            "id": document_id,
            "filename": file.filename,
            "content_type": file.content_type,
            "text_content": text,
            "summary": summary,
            "created_at": datetime.datetime.utcnow()
        }
        
        await db.document_summaries.insert_one(document_data)
        
        return {
            "document_id": document_id,
            "summary": summary,
            "word_count": len(text.split())
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing document: {str(e)}"
        )
    finally:
        # Clean up the temporary file
        os.unlink(temp_file.name)