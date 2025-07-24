from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import JSONResponse
from db.mongo_client import update_user_session
from dependencies import get_user_session_data

job_router = APIRouter(prefix="/job")

@job_router.post("/update_details")
async def update_job_details(
    request: Request,
    job_description: str = Form(...),
    company_details: str = Form(...),
    user_session: dict = Depends(get_user_session_data)
):
    try:
        user_id = request.state.user_id
        update_user_session(
            user_id,
            {
                "job_description": job_description,
                "company_details": company_details
            }
        )

        # Get preview
        job_preview = ' '.join(job_description.split()[:10])
        company_preview = ' '.join(company_details.split()[:10])

        return JSONResponse(
            status_code=200,
            content={
                "message": "Job details uploaded successfully",
                "job_description": job_preview,
                "company_details": company_preview
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing job details: {str(e)}"
        )
