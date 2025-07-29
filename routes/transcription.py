from fastapi import APIRouter, Request, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
import os
import json
import requests
import tempfile
from groq import Groq
from db.mongo_client import update_user_session
from dependencies import get_user_session_data

transcription_router = APIRouter(prefix="/transcribe")

@transcription_router.post("/")
async def transcribe_audio(request: Request, file: UploadFile = File(...), user_session: dict = Depends(get_user_session_data)):
    try:
        # Save file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
            temp_path = temp_file.name
            temp_file.write(await file.read())
                    
        # Initialize the Groq client
        client = Groq(api_key=os.environ.get("GROQ_STT_API_KEY"))

        # Open the audio file
        try:
            with open(temp_path, "rb") as file:
                # Create a transcription of the audio file
                transcription = client.audio.transcriptions.create(
                file=file, # Required audio file
                model="whisper-large-v3-turbo", # Required model to use for transcription
                prompt="This conversation is an interview",  # Optional
                response_format="verbose_json",  # Optional
                timestamp_granularities = ["word", "segment"], # Optional (must set response_format to "json" to use and can specify "word", "segment" (default), or both)
                language="en",  # Optional
                temperature=0.0  # Optional
                )

                text = transcription.text
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Temporary audio file not found.")
        except IOError as e:
            raise HTTPException(status_code=500, detail=f"Error reading temporary audio file: {e}")

        os.remove(temp_path)
        
        # Store the result in MongoDB messages
        user_id = request.state.user_id
        prev_messages = user_session.get("messages", [])
        prev_messages.append({"role": "user", "content": text})
        update_user_session(user_id, {"messages": prev_messages})

        return JSONResponse(
            status_code=200,
            content={
                "message": "Transcription successful",
                "text": text
            }
        )

    except Exception as e:
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing audio: {str(e)}"
        )
