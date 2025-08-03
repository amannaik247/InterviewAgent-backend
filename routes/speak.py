import os
from fastapi import FastAPI, Body, APIRouter, Request, Depends
from fastapi.responses import Response
from dependencies import get_user_session_data
from groq import Groq

speak_router = APIRouter(prefix="/speak")

client = Groq(api_key=os.environ.get("GROQ_STT_API_KEY"))

MODEL = "playai-tts"
FORMAT = "wav"

@speak_router.post("/speak_up")
async def speak(
    request: Request,
    text: str = Body(..., embed=True),
    voice: str = Body(..., embed=True),
    user_session: dict = Depends(get_user_session_data)
):
    try:
        user_id = request.state.user_id

        # Call Groq TTS
        response = client.audio.speech.create(
            model=MODEL,
            voice=voice,
            speed = 1.2,
            input=text,
            response_format=FORMAT,
        )

        # Get audio bytes (streamed)
        audio_bytes = response.read()  # raw bytes

        # Return as audio response
        return Response(
            content=audio_bytes,
            media_type="audio/wav"
        )

    except Exception as e:
        return {"error": str(e)}
