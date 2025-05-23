"""
Reusable feature extraction pipeline for WSIs.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Tuple

import numpy as np
import numpy.typing as npt
import tiffslide
import torch
from PIL import Image
from torch.utils.data import DataLoader

from spinpath.cache import EmbeddingsCache
from spinpath.client.localmodel import ModelConfiguration # Changed from Model to ModelConfiguration
from spinpath.data import WSIPatches # Assuming WSIPatches is in spinpath.data
from spinpath.extractors.base import PatchFeatureExtractor # Corrected import
from spinpath.patchlib.patch import patch_tissue
from spinpath.patchlib.segment import segment_tissue
from spinpath.quickhash import quickhash

logger = logging.getLogger(__name__)

def extract_features_for_slide(
    slide_path: Path,
    extractor: PatchFeatureExtractor, # Takes an instantiated extractor
    model_config: ModelConfiguration, # Uses ModelConfiguration for patch_size_um
    tissue_mask_path: Path | None,
    num_workers_extraction: int,
    quantize: bool,
) -> Tuple[npt.NDArray[np.float32], npt.NDArray[np.int_]]:
    """
    Extracts features for a single whole slide image.

    Args:
        slide_path: Path to the WSI file.
        extractor: Instantiated PatchFeatureExtractor.
        model_config: ModelConfiguration object containing patch_size_um.
        tissue_mask_path: Optional path to a pre-computed tissue mask.
        num_workers_extraction: Number of workers for the DataLoader during feature extraction.
        quantize: Whether to use quantization (e.g., float16) during feature extraction.

    Returns:
        A tuple containing:
            - embedding: npt.NDArray[np.float32] - The extracted feature embeddings.
            - coords: npt.NDArray[np.int_] - The patch coordinates.
    """
    logger.info(f"Starting feature extraction for slide: {slide_path}")

    tslide = tiffslide.TiffSlide(slide_path)
    logger.debug(f"TiffSlide loaded for {slide_path}")

    # Segment tissue
    if tissue_mask_path:
        logger.info(f"Loading pre-computed tissue mask from: {tissue_mask_path}")
        with Image.open(tissue_mask_path) as tissue_mask_img:
            tissue_mask_img.load()
        tissue_mask = tissue_mask_img.convert("1")
    else:
        logger.info(f"No pre-computed mask provided. Segmenting tissue for: {slide_path}")
        tissue_mask_arr = segment_tissue(
            tslide=tslide,
            thumbsize=(2048, 2048), # Consider making these configurable
            median_filter_size=7,
            binary_threshold=7,
            closing_kernel_size=6,
            min_object_size_um2=200**2,
            min_hole_size_um2=190**2,
        )
        tissue_mask = Image.fromarray(tissue_mask_arr).convert("1")
    
    # Validate tissue mask and slide aspect ratio
    tissue_mask_aspect = tissue_mask.size[0] / tissue_mask.size[1]
    slide_aspect = tslide.dimensions[0] / tslide.dimensions[1]
    if not np.isclose(slide_aspect, tissue_mask_aspect, atol=1e-2): # Increased tolerance slightly
        # Log warning instead of raising error to be more robust for slight differences
        logger.warning(
            f"Aspect ratio of slide and tissue mask are not close for {slide_path}:"
            f" slide_aspect={slide_aspect:.4f}, mask_aspect={tissue_mask_aspect:.4f}. "
            f"Ensure masks correctly correspond to slides."
        )

    binary_tissue_mask = np.asarray(tissue_mask) > 0
    logger.info(f"Generating patch coordinates for {slide_path} using patch_size_um: {model_config.patch_size_um}")
    coords = patch_tissue(
        tslide,
        binary_tissue_mask=binary_tissue_mask,
        patch_size_um=model_config.patch_size_um,
    )
    logger.info(f"Generated {len(coords)} patch coordinates.")

    if len(coords) == 0:
        logger.warning(f"No patches generated for slide {slide_path}. Returning empty embeddings and coordinates.")
        return np.array([], dtype=np.float32).reshape(0, extractor.embed_dim if hasattr(extractor, 'embed_dim') else 0), \
               np.array([], dtype=np.int_).reshape(0,2)


    slide_quickhash = quickhash(tslide)
    embeddings_cache = EmbeddingsCache(
        slide_path=slide_path,
        slide_quickhash=slide_quickhash,
        tissue_mask=tissue_mask, # Pass the PIL.Image object
        patch_coordinates=coords,
        embedding_model_name=extractor.name, # extractor is already instantiated
    )

    embedding = embeddings_cache.load()
    if embedding is not None:
        logger.info(f"Loaded embeddings from cache for {slide_path}")
    else:
        logger.info(f"No cached embeddings found for {slide_path}. Extracting features.")
        dataset = WSIPatches(
            wsi_path=slide_path, # Already a Path object
            patch_coordindates=coords,
            transform=extractor.transform, # extractor is instantiated
        )

        if num_workers_extraction == 0:
            # Manually call worker_init if num_workers is 0, as DataLoader won't.
            # This is important if WSIPatches.worker_init() does critical setup like opening the slide.
            logger.debug("num_workers_extraction is 0, calling dataset.worker_init() manually.")
            dataset.worker_init()

        loader = DataLoader(
            dataset,
            batch_size=64, # This batch size is for the feature extractor, not MIL model
            shuffle=False,
            num_workers=num_workers_extraction,
            worker_init_fn=dataset.worker_init if num_workers_extraction > 0 else None,
            # pin_memory=True if torch.cuda.is_available() else False # Optional optimization
        )
        
        # Ensure extractor is on the correct device (can be set by user via cli)
        # extractor.model.to(extractor.device) # model is _model, device is part of extractor
        
        logger.info(f"Running feature extraction with extractor: {extractor.name} on device: {extractor.device}")
        if quantize and extractor.device.type == 'cuda': # Autocast typically for CUDA
            logger.info("Using autocast (float16) for feature extraction.")
            with torch.autocast(device_type=extractor.device.type, dtype=torch.float16):
                embedding = extractor.run(loader)
        else:
            if quantize and extractor.device.type != 'cuda':
                logger.warning("Quantization (autocast) requested but device is not CUDA. Proceeding without autocast.")
            embedding = extractor.run(loader)
        
        embeddings_cache.save(embedding)
        logger.info(f"Saved extracted embeddings to cache for {slide_path}")

    return embedding, coords