from fastapi import APIRouter, Request, Depends, HTTPException, UploadFile
from db.mongo_client import update_user_session
from dependencies import get_user_session_data
from services.groq_api import get_llm_response
import datetime
import fitz  # PyMuPDF
import tempfile
import os
import re

from db.mongo_client import get_collection

router = APIRouter()

def clean_resume_text(raw_text: str) -> str:
    """Clean up resume text by removing excess blank lines and whitespace"""
    text = re.sub(r"\n\s*\n+", "\n\n", raw_text)  # Multiple newlines → 2 max
    lines = [line.strip() for line in text.splitlines()]
    non_empty_lines = [line for line in lines if line]
    return "\n".join(non_empty_lines)

def summarize_resume(resume_text: str) -> str:
    prompt = f"""
    Extract key information from this resume in a structured format for LLM processing:

    REQUIRED SECTIONS:
    - Name (full name only, no contact info)
    - Education (degrees, institutions, graduation years)
    - Work Experience (company, title, duration, 2-3 key responsibilities each)
    - Projects (name, technologies, brief outcome)
    - Skills (technical skills only, categorized)
    - Certifications (if any)

    OUTPUT FORMAT:
    Use clear headings with ** and bullet points. Keep each bullet point to 1-2 lines maximum. Be extremely concise - use short, impactful sentences with key details only. If a section is missing, write "Not specified". Focus on quantifiable achievements and technical details. Avoid unnecessary words and filler content and gaps in lines

    Resume text:
    {resume_text}
    """
    try:
        summary = get_llm_response(
            prompt=prompt,
            messages=[],
            model="meta-llama/llama-4-maverick-17b-128e-instruct"
        )
        return summary
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to summarize resume: {str(e)}"
        )

@router.post("/upload", tags=["Resume"])
async def upload_resume(request: Request, file: UploadFile, user_session: dict = Depends(get_user_session_data)):
    try:
        # Save PDF temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            contents = await file.read()
            temp_file.write(contents)
            temp_file.flush()
            temp_path = temp_file.name

        # Extract raw text
        text_pages = []
        with fitz.open(temp_path) as doc:
            for page in doc:
                text_pages.append(page.get_text())

        full_text = "\n\n".join(text_pages)
        os.remove(temp_path)

        # Store raw text in MongoDB
        resume_doc = {
            "filename": file.filename,
            "text_content": full_text,  # Raw form saved
            "page_count": len(text_pages),
            "upload_time": datetime.datetime.utcnow()
        }

        collection = get_collection("resumes")
        result = collection.insert_one(resume_doc)

        # Clean text for session use
        cleaned_text = clean_resume_text(full_text)
        user_id = request.state.user_id
        # Summarize the cleaned resume text
        summarized_resume = summarize_resume(cleaned_text)
        # Store the summarized resume in the user session
        update_user_session(user_id, {"summarized_resume": summarized_resume})

        return {
            "success": True,
            "message": "Resume uploaded and processed successfully.",
            "parsed_data": {
                "id": str(result.inserted_id),
                "filename": file.filename,
                "page_count": len(text_pages),
                "snippet": summarized_resume[:500] + "..." if len(summarized_resume) > 500 else summarized_resume
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Resume processing failed: {e}")
