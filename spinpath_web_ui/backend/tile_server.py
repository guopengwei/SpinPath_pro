"""
SpinPath Tile Server Module

Comprehensive tile serving system for whole slide images (WSI) inspired by Cytomine-IMS
and modern web-based pathology viewers. Supports multiple image formats through OpenSlide
and provides efficient tile access via HTTP range requests.
"""

import os
import io
import math
import json
import hashlib
from typing import Optional, Tuple, Dict, Any, List
from pathlib import Path
from PIL import Image
import numpy as np
from fastapi import HTTPException
from functools import lru_cache
import logging

# Optional imports with graceful fallbacks
try:
    import openslide
    OPENSLIDE_AVAILABLE = True
except ImportError:
    OPENSLIDE_AVAILABLE = False
    logging.warning("OpenSlide not available. WSI support will be limited.")

try:
    import tiffslide
    TIFFSLIDE_AVAILABLE = True
except ImportError:
    TIFFSLIDE_AVAILABLE = False
    logging.warning("TiffSlide not available. Some TIFF formats may not be supported.")

logger = logging.getLogger(__name__)

class TileServerError(Exception):
    """Custom exception for tile server errors"""
    pass

class WSIInfo:
    """Information about a whole slide image"""
    def __init__(self, slide_path: str):
        self.slide_path = slide_path
        self.slide = None
        self.format = None
        self.dimensions = None
        self.level_count = None
        self.level_dimensions = []
        self.level_downsamples = []
        self.tile_size = (256, 256)  # Default tile size
        self.properties = {}
        self.mpp_x = None  # Microns per pixel X
        self.mpp_y = None  # Microns per pixel Y
        self.objective_power = None
        
        self._load_slide()
    
    def _load_slide(self):
        """Load slide and extract metadata"""
        try:
            if OPENSLIDE_AVAILABLE and openslide.OpenSlide.detect_format(self.slide_path):
                self.slide = openslide.OpenSlide(self.slide_path)
                self.format = "openslide"
                self._load_openslide_metadata()
            elif TIFFSLIDE_AVAILABLE:
                self.slide = tiffslide.TiffSlide(self.slide_path)
                self.format = "tiffslide"
                self._load_tiffslide_metadata()
            else:
                # Fallback to PIL for basic image formats
                self.slide = Image.open(self.slide_path)
                self.format = "pil"
                self._load_pil_metadata()
                
        except Exception as e:
            raise TileServerError(f"Failed to load slide {self.slide_path}: {str(e)}")
    
    def _load_openslide_metadata(self):
        """Load metadata from OpenSlide"""
        self.dimensions = self.slide.dimensions
        self.level_count = self.slide.level_count
        self.level_dimensions = self.slide.level_dimensions
        self.level_downsamples = self.slide.level_downsamples
        self.properties = dict(self.slide.properties)
        
        # Extract microns per pixel
        if openslide.PROPERTY_NAME_MPP_X in self.properties:
            self.mpp_x = float(self.properties[openslide.PROPERTY_NAME_MPP_X])
        if openslide.PROPERTY_NAME_MPP_Y in self.properties:
            self.mpp_y = float(self.properties[openslide.PROPERTY_NAME_MPP_Y])
        
        # Extract objective power
        if openslide.PROPERTY_NAME_OBJECTIVE_POWER in self.properties:
            self.objective_power = float(self.properties[openslide.PROPERTY_NAME_OBJECTIVE_POWER])
    
    def _load_tiffslide_metadata(self):
        """Load metadata from TiffSlide"""
        self.dimensions = self.slide.dimensions
        self.level_count = self.slide.level_count
        self.level_dimensions = self.slide.level_dimensions
        self.level_downsamples = self.slide.level_downsamples
        self.properties = dict(self.slide.properties)
    
    def _load_pil_metadata(self):
        """Load metadata from PIL (basic images)"""
        self.dimensions = self.slide.size
        self.level_count = 1
        self.level_dimensions = [self.dimensions]
        self.level_downsamples = [1.0]
        self.properties = {}
    
    def get_tile(self, level: int, x: int, y: int, tile_size: Tuple[int, int] = None) -> Image.Image:
        """Extract a tile from the slide"""
        if tile_size is None:
            tile_size = self.tile_size
            
        if level >= self.level_count:
            raise TileServerError(f"Level {level} exceeds maximum level {self.level_count - 1}")
        
        try:
            if self.format == "openslide":
                return self._get_openslide_tile(level, x, y, tile_size)
            elif self.format == "tiffslide":
                return self._get_tiffslide_tile(level, x, y, tile_size)
            else:
                return self._get_pil_tile(level, x, y, tile_size)
        except Exception as e:
            raise TileServerError(f"Failed to extract tile ({level}, {x}, {y}): {str(e)}")
    
    def _get_openslide_tile(self, level: int, x: int, y: int, tile_size: Tuple[int, int]) -> Image.Image:
        """Get tile using OpenSlide"""
        # Calculate the region coordinates in level 0
        downsample = self.level_downsamples[level]
        region_x = int(x * tile_size[0] * downsample)
        region_y = int(y * tile_size[1] * downsample)
        
        # Read the region
        tile = self.slide.read_region((region_x, region_y), level, tile_size)
        
        # Convert RGBA to RGB if necessary
        if tile.mode == 'RGBA':
            # Create a white background
            background = Image.new('RGB', tile.size, (255, 255, 255))
            background.paste(tile, mask=tile.split()[-1])  # Use alpha channel as mask
            tile = background
        
        return tile
    
    def _get_tiffslide_tile(self, level: int, x: int, y: int, tile_size: Tuple[int, int]) -> Image.Image:
        """Get tile using TiffSlide"""
        # Similar to OpenSlide implementation
        downsample = self.level_downsamples[level]
        region_x = int(x * tile_size[0] * downsample)
        region_y = int(y * tile_size[1] * downsample)
        
        tile = self.slide.read_region((region_x, region_y), level, tile_size)
        
        if tile.mode == 'RGBA':
            background = Image.new('RGB', tile.size, (255, 255, 255))
            background.paste(tile, mask=tile.split()[-1])
            tile = background
        
        return tile
    
    def _get_pil_tile(self, level: int, x: int, y: int, tile_size: Tuple[int, int]) -> Image.Image:
        """Get tile using PIL (for non-pyramidal images)"""
        # Calculate the region
        region_x = x * tile_size[0]
        region_y = y * tile_size[1]
        
        # Extract the region
        box = (region_x, region_y, 
               min(region_x + tile_size[0], self.dimensions[0]),
               min(region_y + tile_size[1], self.dimensions[1]))
        
        tile = self.slide.crop(box)
        
        # Pad if necessary
        if tile.size != tile_size:
            padded = Image.new('RGB', tile_size, (255, 255, 255))
            padded.paste(tile, (0, 0))
            tile = padded
        
        return tile
    
    def get_thumbnail(self, max_size: Tuple[int, int] = (256, 256)) -> Image.Image:
        """Get a thumbnail of the slide"""
        try:
            if self.format in ["openslide", "tiffslide"]:
                # Use the lowest resolution level for thumbnail
                lowest_level = self.level_count - 1
                level_dims = self.level_dimensions[lowest_level]
                
                # Calculate appropriate size maintaining aspect ratio
                ratio = min(max_size[0] / level_dims[0], max_size[1] / level_dims[1])
                thumb_size = (int(level_dims[0] * ratio), int(level_dims[1] * ratio))
                
                # Get the entire lowest level
                thumb = self.slide.read_region((0, 0), lowest_level, level_dims)
                
                # Resize to thumbnail size
                if thumb.mode == 'RGBA':
                    background = Image.new('RGB', thumb.size, (255, 255, 255))
                    background.paste(thumb, mask=thumb.split()[-1])
                    thumb = background
                
                thumb = thumb.resize(thumb_size, Image.LANCZOS)
                
            else:
                # For PIL images
                thumb = self.slide.copy()
                thumb.thumbnail(max_size, Image.LANCZOS)
            
            return thumb
        except Exception as e:
            raise TileServerError(f"Failed to generate thumbnail: {str(e)}")
    
    def close(self):
        """Close the slide"""
        if hasattr(self.slide, 'close'):
            self.slide.close()

class TileServer:
    """Main tile server class"""
    
    def __init__(self, cache_size: int = 128):
        self.cache_size = cache_size
        self._slide_cache = {}
        self._tile_cache = {}
        
    @lru_cache(maxsize=32)
    def get_slide_info(self, slide_path: str) -> Dict[str, Any]:
        """Get slide information with caching"""
        slide_info = self._get_or_create_slide(slide_path)
        
        return {
            "format": slide_info.format,
            "dimensions": slide_info.dimensions,
            "level_count": slide_info.level_count,
            "level_dimensions": slide_info.level_dimensions,
            "level_downsamples": slide_info.level_downsamples,
            "tile_size": slide_info.tile_size,
            "mpp_x": slide_info.mpp_x,
            "mpp_y": slide_info.mpp_y,
            "objective_power": slide_info.objective_power,
            "properties": slide_info.properties
        }
    
    def _get_or_create_slide(self, slide_path: str) -> WSIInfo:
        """Get slide from cache or create new one"""
        if slide_path not in self._slide_cache:
            if len(self._slide_cache) >= self.cache_size:
                # Remove oldest slide
                oldest_key = next(iter(self._slide_cache))
                self._slide_cache[oldest_key].close()
                del self._slide_cache[oldest_key]
            
            self._slide_cache[slide_path] = WSIInfo(slide_path)
        
        return self._slide_cache[slide_path]
    
    def get_tile(self, slide_path: str, level: int, x: int, y: int, 
                 format: str = "JPEG", quality: int = 85) -> bytes:
        """Get a tile as bytes"""
        # Create cache key
        cache_key = f"{slide_path}:{level}:{x}:{y}:{format}:{quality}"
        
        if cache_key in self._tile_cache:
            return self._tile_cache[cache_key]
        
        # Get the slide
        slide_info = self._get_or_create_slide(slide_path)
        
        # Extract the tile
        tile = slide_info.get_tile(level, x, y)
        
        # Convert to bytes
        tile_bytes = self._image_to_bytes(tile, format, quality)
        
        # Cache the result
        if len(self._tile_cache) >= self.cache_size * 10:  # Allow more tiles in cache
            # Remove some old tiles
            keys_to_remove = list(self._tile_cache.keys())[:self.cache_size]
            for key in keys_to_remove:
                del self._tile_cache[key]
        
        self._tile_cache[cache_key] = tile_bytes
        
        return tile_bytes
    
    def get_thumbnail(self, slide_path: str, max_size: Tuple[int, int] = (256, 256),
                     format: str = "JPEG", quality: int = 85) -> bytes:
        """Get a thumbnail as bytes"""
        slide_info = self._get_or_create_slide(slide_path)
        thumbnail = slide_info.get_thumbnail(max_size)
        return self._image_to_bytes(thumbnail, format, quality)
    
    def _image_to_bytes(self, image: Image.Image, format: str = "JPEG", quality: int = 85) -> bytes:
        """Convert PIL Image to bytes"""
        buffer = io.BytesIO()
        
        if format.upper() == "JPEG":
            image.save(buffer, format="JPEG", quality=quality)
        elif format.upper() == "PNG":
            image.save(buffer, format="PNG")
        elif format.upper() == "WEBP":
            image.save(buffer, format="WEBP", quality=quality)
        else:
            image.save(buffer, format="JPEG", quality=quality)
        
        buffer.seek(0)
        return buffer.getvalue()
    
    def get_dzi_descriptor(self, slide_path: str) -> str:
        """Generate Deep Zoom Image (DZI) descriptor XML"""
        slide_info = self._get_or_create_slide(slide_path)
        
        # Calculate max level based on tile size
        max_dim = max(slide_info.dimensions)
        max_level = math.ceil(math.log2(max_dim / slide_info.tile_size[0])) + 1
        
        dzi_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Image TileSize="{slide_info.tile_size[0]}" Overlap="0" Format="jpeg" xmlns="http://schemas.microsoft.com/deepzoom/2008">
    <Size Width="{slide_info.dimensions[0]}" Height="{slide_info.dimensions[1]}"/>
</Image>'''
        
        return dzi_xml
    
    def get_tile_grid_info(self, slide_path: str, level: int) -> Dict[str, int]:
        """Get information about the tile grid for a specific level"""
        slide_info = self._get_or_create_slide(slide_path)
        
        if level >= slide_info.level_count:
            raise TileServerError(f"Level {level} exceeds maximum level {slide_info.level_count - 1}")
        
        level_dims = slide_info.level_dimensions[level]
        tile_cols = math.ceil(level_dims[0] / slide_info.tile_size[0])
        tile_rows = math.ceil(level_dims[1] / slide_info.tile_size[1])
        
        return {
            "level": level,
            "columns": tile_cols,
            "rows": tile_rows,
            "tile_width": slide_info.tile_size[0],
            "tile_height": slide_info.tile_size[1],
            "level_width": level_dims[0],
            "level_height": level_dims[1]
        }
    
    def clear_cache(self):
        """Clear all caches"""
        for slide in self._slide_cache.values():
            slide.close()
        self._slide_cache.clear()
        self._tile_cache.clear()
        self.get_slide_info.cache_clear()

# Global tile server instance
tile_server = TileServer()

# Utility functions for format detection
def detect_slide_format(file_path: str) -> str:
    """Detect the format of a slide file"""
    file_path = Path(file_path)
    extension = file_path.suffix.lower()
    
    # Check if it's a supported WSI format
    if OPENSLIDE_AVAILABLE and openslide.OpenSlide.detect_format(str(file_path)):
        return "openslide"
    elif extension in ['.tif', '.tiff']:
        return "tiff"
    elif extension in ['.jpg', '.jpeg', '.png', '.bmp']:
        return "standard"
    else:
        return "unknown"

def get_supported_formats() -> List[str]:
    """Get list of supported image formats"""
    formats = ["JPEG", "PNG", "BMP"]
    
    if OPENSLIDE_AVAILABLE:
        formats.extend(["SVS", "NDPI", "VMS", "SCN", "MRXS", "BIF", "VSI"])
    
    if TIFFSLIDE_AVAILABLE:
        formats.extend(["TIFF", "OME-TIFF"])
    
    return list(set(formats))

def validate_slide_file(file_path: str) -> bool:
    """Validate if a file is a supported slide format"""
    if not os.path.exists(file_path):
        return False
    
    try:
        format_type = detect_slide_format(file_path)
        return format_type != "unknown"
    except Exception:
        return False 