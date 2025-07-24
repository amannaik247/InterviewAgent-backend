from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional, List
from pydantic import BaseModel
from services.groq_api import get_llm_response
from db.mongo_client import update_user_session, mongo_client
from dependencies import get_user_session_data
from fastapi import APIRouter, Request, Depends, HTTPException
from datetime import datetime

# Initialize router
question_router = APIRouter(prefix="/question")

PROMPT_TEMPLATE = """
You are an AI interviewer conducting a natural, friendly, and progressive job interview.

Your task is to generate ONE concise interview question (1–2 sentences max) using:
- Job Description: {job_desc}
- Company Info: {company_info}
- Resume: {resume_text}
- Conversation History: {conversation_history}

GOAL:
Simulate a real interview — start warm and easy, then gradually go deeper into relevant experience and skills.

RULES:

1. **If no prior message:**
   - Greet the candidate.
   - Ask a soft opener like: “Tell me about yourself” or “What drew you to this role?”

2. **If prior response exists:**
   - Briefly acknowledge it (1 sentence max).
   - Ask a related follow-up that digs deeper.

3. **Tone:**
   - Warm, conversational, and human — like a real interviewer.
   - Avoid robotic or overly formal language.

4. **Content:**
   - Personalize using resume and job info.
   - Ask only one question.
   - Avoid yes/no questions — aim for stories or examples.

5. **Output:**
   - Return only the question (no notes or instructions).
   - Keep it concise (1–2 sentences max).
"""

@question_router.post("/generate")
async def generate_question(
    request: Request,
    user_input: str = None,
    user_session: dict = Depends(get_user_session_data)
):
    try:
        user_id = request.state.user_id
        # Get session data from MongoDB
        job_desc = user_session.get("job_description")
        company_info = user_session.get("company_details")
        resume_text = user_session.get("cleaned_resume_text")

        if not all([job_desc, company_info, resume_text]):
            raise HTTPException(
                status_code=400,
                detail="Missing required session data (job details, company info, or resume)"
            )

        # If user_input is None, it's a new interview, clear messages
        if user_input is None:
            update_user_session(user_id, {"messages": []})
            prev_messages = []
        else:
            prev_messages = user_session.get("messages", [])
            prev_messages.append({"role": "user", "content": user_input})
            update_user_session(user_id, {"messages": prev_messages})
        
        # Create prompt including conversation history
        conversation_history = "\n".join([f'{msg["role"]}: {msg["content"]}' for msg in prev_messages])
        prompt = PROMPT_TEMPLATE.format(
            job_desc=job_desc,
            company_info=company_info,
            resume_text=resume_text,
            conversation_history=conversation_history
        )
        
        try:
            question = get_llm_response(
                prompt=prompt,
                messages=prev_messages,
                model="llama-3.3-70b-versatile"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate question: {str(e)}"
            )
        
        # Store response in MongoDB
        prev_messages.append({"role": "assistant", "content": question})
        
        # Use user_id as the interview identifier
        interview_data = {
            "user_id": user_id,
            "job_description": job_desc,
            "company_details": company_info,
            "resume_text": resume_text,
            "conversation": prev_messages,
            "start_time": datetime.utcnow()
        }
        
        # Upsert the interview document using user_id as the unique key
        mongo_client.db["interviews"].update_one(
            {"user_id": user_id},
            {"$set": interview_data},
            upsert=True
        )
        
        # Update user session with current messages (interview_id is now implicitly user_id)
        update_user_session(user_id, {"messages": prev_messages})

        return JSONResponse(
            status_code=200,
            content={
                "question": question,
                "interview_id": user_id
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating question: {str(e)}"
        )
