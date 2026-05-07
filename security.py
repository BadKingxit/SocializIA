import os
from fastapi import Request, HTTPException, status

API_KEY = os.getenv("API_KEY", "")

async def protect(request: Request):
    if not API_KEY:
        return
    key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    if key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key invalida ou ausente"
        )
