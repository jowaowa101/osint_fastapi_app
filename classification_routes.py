from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .classifier import classify_text

# Register router with a prefix
router = APIRouter()  # ✅ Removed prefix

# Define input model
class TextInput(BaseModel):
    text: str

# Classification route
@router.post("/classify")
def classify(input: TextInput):
    try:
        category = classify_text(input.text)
        return {"category": category}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
