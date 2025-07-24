import os
import requests
from typing import Dict, Any
from dotenv import load_dotenv
load_dotenv(override=True)


def get_llm_response(prompt: str, messages: list[dict] = None, model: str = "llama-3.3-70b-versatile") -> str:
    """
    Calls Groq API with given prompt and messages
    Returns generated text from API
    """
    headers = {
        "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": "You are a helpful assistant."}] + (messages or [])
    }
    if prompt:
        payload["messages"].append({"role": "user", "content": prompt})
    
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload
        )
        
        if response.status_code != 200:
            raise Exception(f"Groq API error: {response.text}")
        
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        raise Exception(f"Error calling Groq API: {str(e)}")

def evaluate_answer(
    user_answer: str,
    job_description: str,
    question: str,
    category: str,
    analysis_criteria: str
) -> str:
    system_prompt = (
        "You are an AI interview evaluator. Your task is to assess a candidate's answer "
        "to an interview question based on a specific category and criteria. "
        "Provide a score from 1 to 10 and a 2-sentence summary explaining the score. "
        "The output MUST be in the format: 'Score: [score]\nSummary: [summary]'."
    )

    user_prompt = (
        f"Candidate's Answer: {user_answer}\n\n"
        f"Job Description: {job_description}\n\n"
        f"Interview Question: {question}\n\n"
        f"Evaluation Category: {category}\n"
        f"Analysis Criteria: {analysis_criteria}\n\n"
        "Please provide a score (1-10) and a 2-sentence summary based on the criteria."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    return get_llm_response(prompt=None, messages=messages)