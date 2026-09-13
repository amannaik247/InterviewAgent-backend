import logging
import traceback
from fastapi import APIRouter, Request, Body, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional
from services.groq_api import get_llm_response
from db.mongo_client import update_user_session, mongo_client
from dependencies import get_user_session_data
from datetime import datetime

logger = logging.getLogger(__name__)

# Initialize router
question_router = APIRouter(prefix="/question")

PROMPT_TEMPLATE = """
You are an experienced, friendly interviewer conducting a job interview. Your goal is to assess the candidate's qualifications, experience, and cultural fit through natural conversation.
Context Information:
Job Description: {job_desc}
Company Information: {company_info}
Candidate Resume: {resume_text}
Conversation History: {conversation_history}
Latest question-answer pair: {latest_qa_pair}

Interview Guidelines:
Response Style:
- Keep responses between 20-40 words maximum
- Sound natural, warm, and conversational like a real interviewer
- Use the candidate's name sparingly and naturally - only when it feels organic, not at the start of every response
- Show genuine interest and enthusiasm
- Ask one question at a time
- Briefly acknowledge their latest response when appropriate ("That's great", "I see", "Interesting"). If latest response is not appropriate, acknowledge with ("Uh interesting", "Hm alright") in a neutral tone and ask for a more appropriate response.

- You MUST use natural conversational sounds occasionally in most responses: "Uh", "Hm", "Umm", "Oh", "Ah", "Right" to reply more like a human who is thinking before speaking
- Create smooth transitions when moving to new topics: "That makes sense. Now I'd like to shift gears and ask about..."

Interview Flow:
If no conversation history exists:
- Start with a warm welcome using their name
- Ask a general opening question about themselves or what brought them to apply

As the interview progresses:
- Begin with general questions about background and motivation
- Gradually move to more specific technical/field knowledge questions
- Reference specific items from their resume (projects, experiences, skills)
- Ask behavioral questions using STAR method prompts
- Include questions related to the job requirements and company culture
- Probe deeper based on their previous answers

Question Types to Include:

Resume-based: "I noticed you worked on [specific project/role], can you tell me more about that?"
Technical/Field knowledge: Ask relevant skills-based questions from the job description
Behavioral: "Tell me about a time when..." scenarios
Company fit: Questions about working style, values, team collaboration
Situational: "How would you handle..." scenarios relevant to the role

Interviewer Personality:

- Professional yet approachable
- Encouraging and supportive
- Curious and engaged
- Occasionally provide brief positive acknowledgments
- Show you're actively listening by referencing their previous responses
- Vary your conversational starters naturally - avoid repetitive patterns like starting every response with the candidate's name

Remember: You're evaluating their qualifications while making them feel comfortable. Ask follow-up questions naturally based on their responses, just like a real interviewer would.
"""

@question_router.post("/generate")
async def generate_question(
    request: Request,
    user_input: Optional[str] = Body(None, embed=True),
    user_session: dict = Depends(get_user_session_data)
):
    try:
        user_id = getattr(request.state, "user_id", None) or request.headers.get("X-User-ID")
        if not user_id:
            raise HTTPException(status_code=400, detail="Missing user_id in request state or headers")

        # Get session data from MongoDB
        job_desc = user_session.get("job_description")
        company_info = user_session.get("company_details")
        resume_text = user_session.get("summarized_resume") or user_session.get("resume_text") or "Standard candidate background and experience"

        missing = []
        if not job_desc:
            missing.append("job_description")
        if not company_info:
            missing.append("company_details")

        if missing:
            logger.warning(f"User {user_id} missing session keys: {missing}. Found keys in session: {list(user_session.keys())}")
            raise HTTPException(
                status_code=400,
                detail=f"Missing required session data ({', '.join(missing)}). Please submit job details first."
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
        conversation_history = "\n".join([f'Interviewer: {msg["content"]}' if msg['role'] == 'assistant' else f'{msg["role"]}: {msg["content"]}' for msg in prev_messages])
        
        latest_qa_pair = ""
        if len(prev_messages) >= 2:
            last_user_message = next((msg for msg in reversed(prev_messages) if msg['role'] == 'user'), None)
            last_interviewer_message = next((msg for msg in reversed(prev_messages) if msg['role'] == 'assistant'), None)
            if last_interviewer_message and last_user_message:
                latest_qa_pair = f"Interviewer: {last_interviewer_message['content']}\nCandidate: {last_user_message['content']}"

        prompt = PROMPT_TEMPLATE.format(
            job_desc=job_desc,
            company_info=company_info,
            resume_text=resume_text,
            conversation_history=conversation_history,
            latest_qa_pair=latest_qa_pair
        )
        
        try:
            question = get_llm_response(
                prompt=prompt,
                messages=prev_messages,
            )
        except Exception as e:
            logger.error(f"LLM generation failed: {traceback.format_exc()}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate question from LLM: {str(e)}"
            )
        
        # Store response in MongoDB
        prev_messages.append({"role": "assistant", "content": question})
        
        # Update user session with current messages (interview_id is now implicitly user_id)
        update_user_session(user_id, {"messages": prev_messages})

        return JSONResponse(
            status_code=200,
            content={
                "question": question,
                "interview_id": user_id
            }
        )
        
    except HTTPException as http_exc:
        # Re-raise HTTPExceptions directly so status code (e.g. 400 Bad Request) is preserved
        raise http_exc
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Error in /question/generate: {error_trace}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generating question: {str(e)} | Traceback: {error_trace}"
        )

