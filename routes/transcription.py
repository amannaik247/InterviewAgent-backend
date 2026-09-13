from fastapi import APIRouter, Request, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
import os
import tempfile
from groq import Groq
from db.mongo_client import update_user_session
from dependencies import get_user_session_data

transcription_router = APIRouter(prefix="/transcribe")

@transcription_router.post("/")
async def transcribe_audio(request: Request, file: UploadFile = File(...), user_session: dict = Depends(get_user_session_data)):
    temp_path = None
    try:
        # Save uploaded file temporarily
        suffix = os.path.splitext(file.filename)[1] if file.filename else ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = temp_file.name
            temp_file.write(await file.read())
                    
        # Initialize the Groq client
        api_key = os.getenv("GROQ_STT_API_KEY") or os.getenv("GROQ_API_KEY")
        if not api_key:
            raise HTTPException(status_code=401, detail="Groq API key not configured in environment variables.")
        client = Groq(api_key=api_key)

        # Open the audio file and transcribe
        try:
            with open(temp_path, "rb") as audio_file:
                filename = file.filename or "audio.wav"
                transcription = client.audio.transcriptions.create(
                    file=(filename, audio_file),
                    model="whisper-large-v3-turbo",
                    prompt="This conversation is an interview",
                    response_format="verbose_json",
                    timestamp_granularities=["word", "segment"],
                    language="en",
                    temperature=0.0
                )
                text = transcription.text
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Temporary audio file not found.")
        except IOError as e:
            raise HTTPException(status_code=500, detail=f"Error reading temporary audio file: {e}")

        # Store the result in MongoDB messages
        user_id = getattr(request.state, "user_id", user_session.get("user_id"))
        if user_id:
            update_user_session(user_id, {"messages": [{"role": "user", "content": text}]})

        return JSONResponse(
            status_code=200,
            content={
                "message": "Transcription successful",
                "text": text
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing audio: {str(e)}"
        )
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
