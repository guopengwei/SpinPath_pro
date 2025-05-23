"""
SpinPath Web UI Backend

A comprehensive FastAPI backend for the SpinPath whole slide image analysis toolkit.
Provides RESTful APIs for slide management, model inference, and tile serving.
"""

import os
import sys
import io
import uuid
import json
import shutil
import asyncio
import threading
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, asdict

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from tile_server import (
    tile_server, 
    TileServerError, 
    detect_slide_format, 
    get_supported_formats,
    validate_slide_file
)

# Add the parent directory to the Python path to import spinpath
parent_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(parent_dir))

try:
    from spinpath import infer_one_slide
    from spinpath.client.hfmodel import load_torchscript_model_from_hf
    from spinpath.extractors import EXTRACTORS
    from spinpath.output_container import ModelInferenceOutput
    SPINPATH_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import SpinPath: {e}")
    SPINPATH_AVAILABLE = False

app = FastAPI(title="SpinPath Web UI Backend", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://frontend:80"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration for slides directory
SLIDES_BASE_DIR = "uploaded_slides"
if not os.path.exists(SLIDES_BASE_DIR):
    os.makedirs(SLIDES_BASE_DIR)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory databases
slides_db: Dict[str, Dict] = {}
inference_jobs_db: Dict[str, Dict] = {}

# Available models (can be extended)
AVAILABLE_MODELS = [
    {
        "id": "microsoft/ctranspath",
        "name": "CTransPath - Histopathology Feature Extractor",
        "type": "hf_model",
        "description": "Contrastive learning based model for histopathology"
    },
    {
        "id": "owkin/phikon",
        "name": "Phikon - Foundation Model for Pathology",
        "type": "hf_model", 
        "description": "Self-supervised foundation model for computational pathology"
    }
]

class SlideMetadata(BaseModel):
    id: str
    filename: str
    filepath: str
    upload_date: str
    file_size: int

class SlideUploadResponse(BaseModel):
    id: str
    filename: str
    message: str

class InferenceRequest(BaseModel):
    slide_ids: List[str]
    model_id: str
    patch_size_um: Optional[float] = 256.0
    num_workers: Optional[int] = 4

class InferenceJob(BaseModel):
    job_id: str
    status: str
    message: Optional[str] = None
    slide_ids: List[str]
    model_id: str
    created_at: str
    completed_at: Optional[str] = None
    progress: Optional[float] = None

class InferenceResult(BaseModel):
    job_id: str
    slide_id: str
    results: Dict
    class_predictions: List[Dict]
    attention_map: Optional[List] = None

class ModelInfo(BaseModel):
    id: str
    name: str
    type: str
    description: str

def run_inference_background(job_id: str, slide_ids: List[str], model_id: str, patch_size_um: float, num_workers: int):
    """Background task to run actual inference"""
    try:
        if not SPINPATH_AVAILABLE:
            raise Exception("SpinPath library not available")
            
        # Update job status to running
        inference_jobs_db[job_id]["status"] = "RUNNING"
        inference_jobs_db[job_id]["progress"] = 0.0
        
        # Load model
        logger.info(f"Loading model: {model_id}")
        try:
            model = load_torchscript_model_from_hf(model_id)
        except Exception as e:
            logger.error(f"Failed to load model {model_id}: {e}")
            inference_jobs_db[job_id]["status"] = "FAILED"
            inference_jobs_db[job_id]["message"] = f"Failed to load model: {str(e)}"
            return
            
        results = []
        total_slides = len(slide_ids)
        
        for i, slide_id in enumerate(slide_ids):
            try:
                logger.info(f"Processing slide {slide_id} ({i+1}/{total_slides})")
                
                if slide_id not in slides_db:
                    raise Exception(f"Slide {slide_id} not found")
                    
                slide_path = slides_db[slide_id]["filepath"]
                
                # Run inference
                inference_output = infer_one_slide(
                    slide_path=slide_path,
                    model=model,
                    tissue_mask=None,
                    num_workers=num_workers
                )
                
                # Format results
                class_predictions = []
                for class_name, prob in zip(inference_output.class_names, inference_output.softmax_probs[0]):
                    class_predictions.append({
                        "class_name": class_name,
                        "probability": float(prob)
                    })
                
                slide_result = {
                    "slide_id": slide_id,
                    "predictions": class_predictions,
                    "logits": inference_output.logits.tolist(),
                    "attention": inference_output.attention.tolist() if inference_output.attention is not None else None,
                    "patch_coordinates": inference_output.patch_coordinates.tolist() if inference_output.patch_coordinates is not None else None
                }
                
                results.append(slide_result)
                
                # Update progress
                progress = (i + 1) / total_slides
                inference_jobs_db[job_id]["progress"] = progress
                
            except Exception as e:
                logger.error(f"Failed to process slide {slide_id}: {e}")
                slide_result = {
                    "slide_id": slide_id,
                    "error": str(e),
                    "predictions": []
                }
                results.append(slide_result)
        
        # Update job as completed
        inference_jobs_db[job_id]["status"] = "COMPLETED"
        inference_jobs_db[job_id]["results"] = results
        inference_jobs_db[job_id]["completed_at"] = datetime.now().isoformat()
        inference_jobs_db[job_id]["progress"] = 1.0
        logger.info(f"Inference job {job_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Inference job {job_id} failed: {e}")
        inference_jobs_db[job_id]["status"] = "FAILED"
        inference_jobs_db[job_id]["message"] = str(e)
        inference_jobs_db[job_id]["completed_at"] = datetime.now().isoformat()

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

    # Get file size
    file_size = os.path.getsize(filepath)

    slide_meta = {
        "id": slide_id,
        "filename": filename,
        "filepath": filepath,
        "upload_date": datetime.now().isoformat(),
        "file_size": file_size
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

    if filepath_to_delete and os.path.exists(filepath_to_delete):
        try:
            os.remove(filepath_to_delete)
        except Exception as e:
            logger.error(f"Error deleting file {filepath_to_delete}: {e}")

    del slides_db[slide_id]
    return {}

@app.get("/models", response_model=List[ModelInfo])
async def get_available_models():
    return AVAILABLE_MODELS

@app.post("/inference", response_model=InferenceJob)
async def create_inference_job(request: InferenceRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())

    # Validate slide_ids
    for slide_id in request.slide_ids:
        if slide_id not in slides_db:
            raise HTTPException(status_code=404, detail=f"Slide with ID {slide_id} not found.")

    job = {
        "job_id": job_id,
        "status": "PENDING",
        "slide_ids": request.slide_ids,
        "model_id": request.model_id,
        "created_at": datetime.now().isoformat(),
        "message": "Inference job created and pending execution.",
        "progress": 0.0
    }
    inference_jobs_db[job_id] = job
    
    # Start background inference
    background_tasks.add_task(
        run_inference_background, 
        job_id, 
        request.slide_ids, 
        request.model_id,
        request.patch_size_um or 256.0,
        request.num_workers or 4
    )
    
    return InferenceJob(**job)

@app.get("/inference/{job_id}", response_model=InferenceJob)
async def get_inference_job_status(job_id: str):
    job = inference_jobs_db.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Inference job not found")
    return InferenceJob(**job)

@app.get("/inference/results/{job_id}")
async def get_inference_results(job_id: str):
    job = inference_jobs_db.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Inference job not found")

    if job["status"] != "COMPLETED":
        raise HTTPException(status_code=202, detail=f"Results for job {job_id} are not ready. Status: {job['status']}")

    return {
        "job_id": job_id,
        "results": job.get("results", []),
        "status": job["status"]
    }

@app.get("/")
async def root():
    status = "SpinPath library available" if SPINPATH_AVAILABLE else "SpinPath library not available"
    return {
        "message": "SpinPath Web UI Backend",
        "status": status,
        "available_extractors": list(EXTRACTORS.keys()) if SPINPATH_AVAILABLE else [],
        "version": "1.0.0",
        "endpoints": {
            "slides": "/slides",
            "models": "/models", 
            "inference": "/inference",
            "health": "/health"
        }
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "spinpath_available": SPINPATH_AVAILABLE,
        "slides_count": len(slides_db),
        "active_jobs": len([job for job in inference_jobs_db.values() if job["status"] in ["PENDING", "RUNNING"]])
    }

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

# === TILE SERVING ENDPOINTS ===

@app.get("/api/slides/{slide_id}/info")
async def get_slide_info(slide_id: str):
    """Get comprehensive information about a slide"""
    if slide_id not in slides_db:
        raise HTTPException(status_code=404, detail="Slide not found")
    
    slide = slides_db[slide_id]
    
    try:
        # Get tile server info
        tile_info = tile_server.get_slide_info(slide["filepath"])
        
        # Combine with slide metadata
        slide_info = {
            "id": slide["id"],
            "filename": slide["filename"],
            "file_path": slide["filepath"],
            "upload_time": slide["upload_date"],
            "file_size": slide["file_size"],
            "slide_format": tile_info["format"],
            "dimensions": tile_info["dimensions"],
            "level_count": tile_info["level_count"],
            "level_dimensions": tile_info["level_dimensions"],
            "level_downsamples": tile_info["level_downsamples"],
            "tile_size": tile_info["tile_size"],
            "mpp_x": tile_info["mpp_x"],
            "mpp_y": tile_info["mpp_y"],
            "objective_power": tile_info["objective_power"],
            "properties": tile_info["properties"]
        }
        
        return slide_info
        
    except TileServerError as e:
        raise HTTPException(status_code=500, detail=f"Tile server error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.get("/api/slides/{slide_id}/tile/{level}/{x}/{y}")
async def get_tile(
    slide_id: str, 
    level: int, 
    x: int, 
    y: int,
    format: str = "JPEG",
    quality: int = 85
):
    """Get a specific tile from a slide"""
    if slide_id not in slides_db:
        raise HTTPException(status_code=404, detail="Slide not found")
    
    slide = slides_db[slide_id]
    
    try:
        tile_bytes = tile_server.get_tile(
            slide["filepath"], level, x, y, format, quality
        )
        
        # Determine media type
        if format.upper() == "PNG":
            media_type = "image/png"
        elif format.upper() == "WEBP":
            media_type = "image/webp"
        else:
            media_type = "image/jpeg"
        
        return StreamingResponse(
            io.BytesIO(tile_bytes),
            media_type=media_type,
            headers={
                "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
                "X-Tile-Level": str(level),
                "X-Tile-X": str(x),
                "X-Tile-Y": str(y)
            }
        )
        
    except TileServerError as e:
        raise HTTPException(status_code=500, detail=f"Tile server error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.get("/api/slides/{slide_id}/thumbnail")
async def get_thumbnail(
    slide_id: str,
    width: int = 256,
    height: int = 256,
    format: str = "JPEG",
    quality: int = 85
):
    """Get a thumbnail of the slide"""
    if slide_id not in slides_db:
        raise HTTPException(status_code=404, detail="Slide not found")
    
    slide = slides_db[slide_id]
    
    try:
        thumbnail_bytes = tile_server.get_thumbnail(
            slide["filepath"], (width, height), format, quality
        )
        
        # Determine media type
        if format.upper() == "PNG":
            media_type = "image/png"
        elif format.upper() == "WEBP":
            media_type = "image/webp"
        else:
            media_type = "image/jpeg"
        
        return StreamingResponse(
            io.BytesIO(thumbnail_bytes),
            media_type=media_type,
            headers={
                "Cache-Control": "public, max-age=7200",  # Cache for 2 hours
                "X-Thumbnail-Width": str(width),
                "X-Thumbnail-Height": str(height)
            }
        )
        
    except TileServerError as e:
        raise HTTPException(status_code=500, detail=f"Tile server error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.get("/api/slides/{slide_id}/dzi")
async def get_dzi_descriptor(slide_id: str):
    """Get Deep Zoom Image (DZI) descriptor for OpenSeadragon"""
    if slide_id not in slides_db:
        raise HTTPException(status_code=404, detail="Slide not found")
    
    slide = slides_db[slide_id]
    
    try:
        dzi_xml = tile_server.get_dzi_descriptor(slide["filepath"])
        
        return Response(
            content=dzi_xml,
            media_type="application/xml",
            headers={
                "Cache-Control": "public, max-age=86400",  # Cache for 24 hours
                "X-Slide-Format": "DZI"
            }
        )
        
    except TileServerError as e:
        raise HTTPException(status_code=500, detail=f"Tile server error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.get("/api/slides/{slide_id}/level/{level}/grid")
async def get_tile_grid_info(slide_id: str, level: int):
    """Get tile grid information for a specific level"""
    if slide_id not in slides_db:
        raise HTTPException(status_code=404, detail="Slide not found")
    
    slide = slides_db[slide_id]
    
    try:
        grid_info = tile_server.get_tile_grid_info(slide["filepath"], level)
        return grid_info
        
    except TileServerError as e:
        raise HTTPException(status_code=500, detail=f"Tile server error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.get("/api/slides/{slide_id}/region")
async def get_region(
    slide_id: str,
    x: int,
    y: int,
    width: int,
    height: int,
    level: int = 0,
    format: str = "JPEG",
    quality: int = 85
):
    """Get a specific region from the slide"""
    if slide_id not in slides_db:
        raise HTTPException(status_code=404, detail="Slide not found")
    
    slide = slides_db[slide_id]
    
    try:
        # This is a simplified region extraction
        # In a production system, you'd want more sophisticated region handling
        slide_info = tile_server.get_slide_info(slide["filepath"])
        
        if level >= slide_info["level_count"]:
            raise HTTPException(status_code=400, detail="Invalid level")
        
        # Calculate which tiles we need
        tile_size = slide_info["tile_size"]
        start_tile_x = x // tile_size[0]
        start_tile_y = y // tile_size[1]
        end_tile_x = (x + width - 1) // tile_size[0] + 1
        end_tile_y = (y + height - 1) // tile_size[1] + 1
        
        # For now, return the first tile (simplified implementation)
        tile_bytes = tile_server.get_tile(
            slide["filepath"], level, start_tile_x, start_tile_y, format, quality
        )
        
        # Determine media type
        if format.upper() == "PNG":
            media_type = "image/png"
        elif format.upper() == "WEBP":
            media_type = "image/webp"
        else:
            media_type = "image/jpeg"
        
        return StreamingResponse(
            io.BytesIO(tile_bytes),
            media_type=media_type,
            headers={
                "Cache-Control": "public, max-age=1800",  # Cache for 30 minutes
                "X-Region-X": str(x),
                "X-Region-Y": str(y),
                "X-Region-Width": str(width),
                "X-Region-Height": str(height),
                "X-Region-Level": str(level)
            }
        )
        
    except TileServerError as e:
        raise HTTPException(status_code=500, detail=f"Tile server error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.get("/api/server/tile-formats")
async def get_supported_tile_formats():
    """Get list of supported image formats for tile serving"""
    return {
        "input_formats": get_supported_formats(),
        "output_formats": ["JPEG", "PNG", "WEBP"],
        "tile_server_available": True,
        "openslide_available": tile_server._slide_cache.__class__.__module__ != "builtins",
        "version": "1.0.0"
    }

@app.post("/api/server/clear-tile-cache")
async def clear_tile_cache():
    """Clear the tile server cache (admin endpoint)"""
    try:
        tile_server.clear_cache()
        return {"message": "Tile cache cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")

# OpenSeadragon compatible endpoints (alternative URL patterns)
@app.get("/api/slides/{slide_id}/deepzoom/{level}/{x}_{y}.{format}")
async def get_tile_deepzoom_format(
    slide_id: str, 
    level: int, 
    x: int, 
    y: int,
    format: str = "jpg"
):
    """OpenSeadragon/DeepZoom compatible tile endpoint"""
    # Convert format
    if format.lower() in ["jpg", "jpeg"]:
        tile_format = "JPEG"
    elif format.lower() == "png":
        tile_format = "PNG"
    else:
        tile_format = "JPEG"
    
    return await get_tile(slide_id, level, x, y, tile_format)

@app.get("/api/slides/{slide_id}.dzi")
async def get_dzi_descriptor_alt(slide_id: str):
    """Alternative DZI descriptor endpoint"""
    return await get_dzi_descriptor(slide_id)
