import io
import os
import logging
import requests
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from dependencies import get_user_session_data

logger = logging.getLogger(__name__)

load_dotenv(override=True)

speak_router = APIRouter(prefix="/speak")

AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")
DEFAULT_VOICE = "en-US-JennyNeural" 


@speak_router.post("/speak_up")
async def speak(
    request: Request,
    text: str = Body(..., embed=True),
    voice: str = Body(default=None, embed=True),
    user_session: dict = Depends(get_user_session_data)
):
    try:
        api_key = AZURE_SPEECH_KEY
        region = AZURE_SPEECH_REGION

        if not api_key:
            raise HTTPException(
                status_code=401,
                detail="AZURE_SPEECH_KEY is missing. Please set it in your environment variables or speak.py."
            )
        if not region:
            raise HTTPException(
                status_code=500,
                detail="AZURE_SPEECH_REGION is missing. Please set it in your environment variables or speak.py."
            )

        selected_voice = DEFAULT_VOICE

        url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
        headers = {
            "Ocp-Apim-Subscription-Key": api_key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm",
            "User-Agent": "InterviewAgent"
        }

        # Escape special XML characters in text
        escaped_text = (
            text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&apos;")
        )

        ssml = (
            f"<speak version='1.0' xml:lang='en-US'>"
            f"<voice xml:lang='en-US' name='{selected_voice}'>"
            f"{escaped_text}"
            f"</voice>"
            f"</speak>"
        )

        response = requests.post(url, headers=headers, data=ssml.encode("utf-8"))

        if response.status_code != 200:
            logger.error(f"Azure Speech API error ({response.status_code}): {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Azure Speech TTS API error: {response.text}"
            )

        return StreamingResponse(
            io.BytesIO(response.content),
            media_type="audio/wav"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in Azure TTS generation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error in Azure TTS generation: {str(e)}")
