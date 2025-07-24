from fastapi import Request, HTTPException, Depends
from db.mongo_client import get_user_session, update_user_session
import uuid

async def get_user_id(request: Request):
    # The user_id should already be set by the add_user_id_header middleware
    if hasattr(request.state, "user_id") and request.state.user_id:
        return request.state.user_id
    
    # Fallback: This part should ideally not be hit if middleware is correctly configured
    user_id = request.headers.get("X-User-ID")
    if not user_id:
        user_id = str(uuid.uuid4())
    return user_id

async def get_user_session_data(user_id: str = Depends(get_user_id)):
    session_data = get_user_session(user_id)
    if not session_data:
        session_data = {"user_id": user_id, "messages": []}
        update_user_session(user_id, session_data)
    return session_data