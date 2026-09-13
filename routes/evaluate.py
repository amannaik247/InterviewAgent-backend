from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from db.mongo_client import mongo_client
from services.groq_api import evaluate_answer, get_llm_response
from fastapi import APIRouter, Depends, HTTPException
from dependencies import get_user_id
from db.mongo_client import get_user_session, update_user_session

router = APIRouter()

class AnalysisCategory(BaseModel):
    score: int
    summary: str

class AnalysisResult(BaseModel):
    overall_score: float
    overall_summary: str
    communication_clarity: AnalysisCategory
    role_specific_knowledge: AnalysisCategory
    problem_solving_critical_thinking: AnalysisCategory
    soft_skills_behavioral_competency: AnalysisCategory
    engagement_motivation: AnalysisCategory

class ConversationEntry(BaseModel):
    role: str
    content: str

@router.post("/evaluate", response_model=AnalysisResult)
async def evaluate_interview(user_id: str = Depends(get_user_id)):
    user_session = get_user_session(user_id)
    if not user_session:
        raise HTTPException(status_code=404, detail="User session not found")

    conversation: List[ConversationEntry] = user_session.get("messages", [])
    if not conversation:
        raise HTTPException(status_code=400, detail="No conversation data found for evaluation")
        
    job_description = user_session.get("job_description", "")
    full_conversation_text = "\n".join([f"{entry['role']}: {entry['content']}" for entry in conversation])
    
    categories = {
        "communication_clarity": {
            "prompt": "Analyze the candidate's communication and clarity. Score from 1-10. Summarize in 2 sentences: Sentence structure, clarity, filler words, fluency, answer length, coherence, logical flow."
        },
        "role_specific_knowledge": {
            "prompt": "Analyze the candidate's role-specific knowledge and technical depth. Score from 1-10. Summarize in 2 sentences: How well they address technical/domain-specific questions, use of correct terminology and methods, logical explanations of concepts or processes."
        },
        "problem_solving_critical_thinking": {
            "prompt": "Analyze the candidate's problem-solving and critical thinking. Score from 1-10. Summarize in 2 sentences: Whether the answer follows a logical framework (e.g., STAR, cause-effect), creativity in solutions or handling ambiguity, structured thinking."
        },
        "soft_skills_behavioral_competency": {
            "prompt": "Analyze the candidate's soft skills and behavioral competency. Score from 1-10. Summarize in 2 sentences: Emotional tone (e.g., empathy, ownership, humility), teamwork, leadership, handling feedback or conflict, use of personal examples and reflection."
        },
        "engagement_motivation": {
            "prompt": "Analyze the candidate's engagement and motivation. Score from 1-10. Summarize in 2 sentences: Energy and enthusiasm for the role, relevance of their questions or curiosity shown, clear understanding of the company/mission."
        }
    }

    analysis_results = {}
    for category_name, category_info in categories.items():
        try:
            llm_response = evaluate_answer(
                conversation_text=full_conversation_text,
                job_description=job_description,
                category=category_name,
                analysis_criteria=category_info['prompt']
            )
            # The evaluate_answer function returns a string like 'Score: [score]\nSummary: [summary]'
            score_line, summary_line = llm_response.split('\n', 1)
            score = int(score_line.split(': ')[1])
            summary = summary_line.split(': ')[1]
            # Convert Pydantic model to dictionary for MongoDB storage
            analysis_results[category_name] = AnalysisCategory(score=score, summary=summary).dict()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"LLM evaluation failed for {category_name}: {str(e)}")

    # Compute overall score as rounded average
    overall_score = round(sum(v["score"] for v in analysis_results.values()) / len(analysis_results), 1)

    # Generate holistic interviewer summary via LLM
    summary_prompt = (
        f"Full Conversation: {full_conversation_text}\n\n"
        f"Job Description: {job_description}\n\n"
        f"Category Scores: " + ", ".join(f"{k}: {v['score']}/10" for k, v in analysis_results.items()) + "\n\n"
        "As the interviewer, write a concise 3-4 sentence overall opinion of this candidate. "
        "Highlight their strongest quality, one area for improvement, and whether you would recommend them. "
        "Speak directly as the interviewer (e.g., 'The candidate...'). Output only the summary text, no labels or prefixes."
    )
    try:
        overall_summary = get_llm_response(prompt=summary_prompt)
    except Exception:
        overall_summary = "Overall summary could not be generated."

    # Update user session with the analysis results
    full_analysis = {"overall_score": overall_score, "overall_summary": overall_summary, **analysis_results}
    update_user_session(user_id, {"analysis": full_analysis})

    return AnalysisResult(overall_score=overall_score, overall_summary=overall_summary, **analysis_results)