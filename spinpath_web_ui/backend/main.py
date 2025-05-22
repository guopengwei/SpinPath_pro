from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse # Keep if returning actual image bytes later
import io
from pydantic import BaseModel
from typing import List, Dict
import uuid
import os
import shutil

app = FastAPI()

# Configuration for slides directory
SLIDES_BASE_DIR = "uploaded_slides"
if not os.path.exists(SLIDES_BASE_DIR):
    os.makedirs(SLIDES_BASE_DIR)

# In-memory database for slides metadata
slides_db: Dict[str, Dict] = {}

class SlideMetadata(BaseModel):
    id: str
    filename: str
    filepath: str
    # Add more metadata fields as needed, e.g., upload_date, content_type

class SlideUploadResponse(BaseModel):
    id: str
    filename: str
    message: str

@app.post("/slides", response_model=SlideUploadResponse)
async def upload_slide(file: UploadFile = File(...)):
    slide_id = str(uuid.uuid4())
    filename = file.filename
    filepath = os.path.join(SLIDES_BASE_DIR, f"{slide_id}_{filename}")

    try:
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not save file: {e}")
    finally:
        file.file.close()

    slide_meta = {
        "id": slide_id,
        "filename": filename,
        "filepath": filepath,
        # "content_type": file.content_type # Optional: store content type
    }
    slides_db[slide_id] = slide_meta
    return {"id": slide_id, "filename": filename, "message": "Slide uploaded successfully"}

@app.get("/slides", response_model=List[SlideMetadata])
async def get_slides():
    return list(slides_db.values())

@app.get("/slides/{slide_id}", response_model=SlideMetadata)
async def get_slide_metadata(slide_id: str):
    if slide_id not in slides_db:
        raise HTTPException(status_code=404, detail="Slide not found")
    return slides_db[slide_id]

@app.delete("/slides/{slide_id}", status_code=204)
async def delete_slide(slide_id: str):
    if slide_id not in slides_db:
        raise HTTPException(status_code=404, detail="Slide not found")
    
    slide_info = slides_db[slide_id]
    filepath_to_delete = slide_info.get("filepath")

    # Delete the file from the filesystem
    if filepath_to_delete and os.path.exists(filepath_to_delete):
        try:
            os.remove(filepath_to_delete)
        except Exception as e:
            # Log the error, but don't necessarily block DB removal if file system delete fails
            print(f"Error deleting file {filepath_to_delete}: {e}") 
            # Depending on requirements, you might want to raise HTTPException here
            # raise HTTPException(status_code=500, detail=f"Could not delete slide file: {e}")

    # Delete metadata from DB
    del slides_db[slide_id]
    return {} # Return empty response with 204 status code

@app.get("/")
async def root():
    return {"message": "SpinPath Web UI Backend - Slide Management Setup"}


# Pydantic models for Inference Management
class InferenceRequest(BaseModel):
    slide_ids: List[str]
    model_name: str

class InferenceJob(BaseModel):
    job_id: str
    status: str
    message: str | None = None
    slide_ids: List[str]
    model_name: str

class InferenceResult(BaseModel):
    job_id: str
    results: Dict

# In-memory database for inference jobs
inference_jobs_db: Dict[str, InferenceJob] = {}

@app.post("/inference", response_model=InferenceJob)
async def create_inference_job(request: InferenceRequest):
    job_id = str(uuid.uuid4())

    # Validate slide_ids
    for slide_id in request.slide_ids:
        if slide_id not in slides_db:
            raise HTTPException(status_code=404, detail=f"Slide with ID {slide_id} not found.")

    job = InferenceJob(
        job_id=job_id,
        status="PENDING",
        slide_ids=request.slide_ids,
        model_name=request.model_name,
        message="Inference job created and pending execution."
    )
    inference_jobs_db[job_id] = job
    return job

@app.get("/inference/{job_id}", response_model=InferenceJob)
async def get_inference_job_status(job_id: str):
    job = inference_jobs_db.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Inference job not found")
    return job

@app.get("/inference/results/{job_id}", response_model=InferenceResult)
async def get_inference_results(job_id: str):
    job = inference_jobs_db.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Inference job not found")

    if job.status != "COMPLETED": # Assuming a "COMPLETED" status means results are ready
        raise HTTPException(status_code=202, detail=f"Results for job {job_id} are not ready. Status: {job.status}")

    # Placeholder results
    return InferenceResult(
        job_id=job_id,
        results={"prediction": "This is a placeholder result.", "confidence": 0.95}
    )


@app.get("/slides/{slide_id}/tile/{level}/{z}/{x}/{y}")
async def get_slide_tile(slide_id: str, level: int, z: int, x: int, y: int):
    if slide_id not in slides_db:
        raise HTTPException(status_code=404, detail="Slide not found")

    # Placeholder response
    # In a real implementation, this would read a tile from the slide image
    # using openslide-python or a similar library and return image bytes.
    return {
        "message": "Tile placeholder",
        "slide_id": slide_id,
        "level": level,
        "tile_coordinates": f"{z}/{x}/{y}"
    }
