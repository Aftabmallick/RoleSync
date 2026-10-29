from fastapi import APIRouter
from app.api.v1.endpoints import auth, tailor, outreach, telemetry, profile, application, cover_letter

api_v1_router = APIRouter()
api_v1_router.include_router(auth.router)
api_v1_router.include_router(tailor.router)
api_v1_router.include_router(outreach.router)
api_v1_router.include_router(telemetry.router)
api_v1_router.include_router(profile.router)
api_v1_router.include_router(application.router)
api_v1_router.include_router(cover_letter.router)




