from fastapi import APIRouter, Query
from memory.semantic import get_facts
from memory.emotional_state_db import load_state

router = APIRouter(prefix="/memory", tags=["memory"])

@router.get("/facts")
def read_facts(user_id: str = Query(...), subject: str = None):
    facts = get_facts(user_id, subject=subject)
    return {"user_id": user_id, "count": len(facts), "facts": facts}

@router.get("/state")
def read_state(user_id: str = Query(...)):
    state = load_state(user_id)
    if not state:
        return {"user_id": user_id, "found": False, "state": None}
    return {"user_id": user_id, "found": True, "state": state}
