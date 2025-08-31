from fastapi import APIRouter, UploadFile, File
import easyocr

router = APIRouter(prefix="/image-text", tags=["Image Text Analysis"])

reader = easyocr.Reader(['en'])

@router.post("/extract")
async def extract_text(file: UploadFile = File(...)):
    try:
        image_bytes = await file.read()
        results = reader.readtext(image_bytes)

        # Convert everything to JSON-friendly format
        json_results = []
        for res in results:
            bbox, text, confidence = res
            json_results.append({
                "bbox": [list(map(float, point)) for point in bbox],  # convert np.array to list
                "text": text,
                "confidence": float(confidence)  # convert numpy float/int to Python float
            })

        extracted_text = "\n".join([r["text"] for r in json_results])

        return {"text": extracted_text, "details": json_results}

    except Exception as e:
        return {"error": str(e)}
