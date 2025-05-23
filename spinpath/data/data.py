"""Read patches from whole slide images and provides datasets for training."""

from __future__ import annotations

import logging # Added
from pathlib import Path
from typing import Callable, Sequence, Tuple, Any # Added Tuple, Any

import numpy as np
import numpy.typing as npt
import pandas as pd # Added
import torch
from PIL import Image
from tiffslide import TiffSlide
from torch.utils.data import Dataset

# Imports for WSITrainingDataset
from spinpath.client.localmodel import ModelConfiguration
from spinpath.extractors.base import PatchFeatureExtractor
from spinpath.feature_pipeline import extract_features_for_slide # Added

logger = logging.getLogger(__name__) # Added


class WSIPatches(Dataset):
    """Dataset of one whole slide image.

    This object retrieves patches from a whole slide image on the fly.

    Parameters
    ----------
    wsi_path : str, Path
        Path to whole slide image file.
    patch_path : str, Path
        Path to npy file with coordinates of input image.
    um_px : float
        Scale of the resulting patches. For example, 0.5 for ~20x magnification.
    patch_size : int
        The size of patches in pixels.
    transform : callable, optional
        A callable to modify a retrieved patch. The callable must accept a
        PIL.Image.Image instance and return a torch.Tensor.
    """

    def __init__(
        self,
        wsi_path: str | Path,
        patch_coordindates: npt.NDArray[np.int_],
        transform: Callable[[Image.Image], torch.Tensor],
    ):
        self.wsi_path = wsi_path
        self.patch_coordindates = patch_coordindates
        self.transform = transform

        if not Path(wsi_path).exists():
            raise FileNotFoundError(f"WSI path not found: {wsi_path}")

        assert self.patch_coordindates.ndim == 2, (
            "expected 2D array of patch coordinates"
        )
        # x, y, width, height
        assert self.patch_coordindates.shape[1] == 4, (
            "expected second dimension to have len 4"
        )

    def worker_init(self, worker_id: int | None = None) -> None:
        del worker_id
        self.slide = TiffSlide(self.wsi_path)

    def __len__(self) -> int:
        return len(self.patch_coordindates)

    def __getitem__(self, idx: int) -> torch.Tensor:
        coords: Sequence[int] = self.patch_coordindates[idx]
        assert len(coords) == 4, "expected 4 coords (minx, miny, width, height)"
        minx, miny, width, height = coords
        patch_im: Image.Image = self.slide.read_region(
            location=(minx, miny), level=0, size=(width, height)
        )
        patch_im = patch_im.convert("RGB")
        patch_tensor = self.transform(patch_im)

        return patch_tensor


class WSITrainingDataset(Dataset):
    """
    Dataset for training MIL models. It processes a list of WSIs,
    extracts features for each using a specified feature extractor,
    and returns the features along with labels.
    """
    def __init__(
        self,
        dataset_csv_path: Path,
        feature_extractor: PatchFeatureExtractor,
        model_config: ModelConfiguration,
        num_workers_extraction: int,
        quantize_extraction: bool,
        label_transform: Callable[[Any], int] | None = None, # e.g. lambda x: int(x)
    ):
        """
        Args:
            dataset_csv_path: Path to the CSV file with columns 'slide_path', 'label',
                              and optionally 'mask_path'.
            feature_extractor: Instantiated feature extractor.
            model_config: ModelConfiguration object.
            num_workers_extraction: Number of workers for feature extraction DataLoader.
            quantize_extraction: Whether to quantize during feature extraction.
            label_transform: Optional callable to transform raw labels from CSV.
        """
        super().__init__()
        self.feature_extractor = feature_extractor
        self.model_config = model_config
        self.num_workers_extraction = num_workers_extraction
        self.quantize_extraction = quantize_extraction
        self.label_transform = label_transform

        logger.info(f"Loading dataset CSV from: {dataset_csv_path}")
        try:
            self.slides_df = pd.read_csv(dataset_csv_path)
        except FileNotFoundError:
            logger.error(f"Dataset CSV not found: {dataset_csv_path}")
            raise
        except Exception as e:
            logger.error(f"Error parsing dataset CSV {dataset_csv_path}: {e}")
            raise

        # Validate CSV columns
        required_cols = ["slide_path", "label"]
        for col in required_cols:
            if col not in self.slides_df.columns:
                raise ValueError(f"Dataset CSV must contain column: '{col}'")
        
        if "mask_path" not in self.slides_df.columns:
            logger.info("'mask_path' column not found in CSV. Will proceed without pre-computed masks for all slides.")
            self.slides_df["mask_path"] = None # Ensure column exists, filled with None

        logger.info(f"Successfully loaded {len(self.slides_df)} records from {dataset_csv_path}.")

    def __len__(self) -> int:
        return len(self.slides_df)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Retrieves features and label for a single WSI.

        Returns:
            A tuple containing:
                - embeddings: torch.Tensor of shape (num_patches, feature_dim)
                - label: torch.Tensor (scalar)
                - patch_coords: torch.Tensor of shape (num_patches, 2) - for reference
        """
        slide_info = self.slides_df.iloc[idx]
        slide_path = Path(slide_info["slide_path"])
        raw_label = slide_info["label"]
        mask_path_val = slide_info["mask_path"]
        
        # Handle potentially missing mask_path (if column was missing or value is NaN/None)
        tissue_mask_path: Path | None = None
        if pd.notna(mask_path_val) and mask_path_val:
            tissue_mask_path = Path(mask_path_val)
            if not tissue_mask_path.exists():
                logger.warning(f"Mask path {tissue_mask_path} for slide {slide_path} does not exist. Proceeding without mask.")
                tissue_mask_path = None
        
        logger.debug(f"Processing slide {idx}: {slide_path}, Label: {raw_label}, Mask: {tissue_mask_path}")

        # Extract features for the slide
        # This function handles caching internally.
        embeddings_np, patch_coords_np = extract_features_for_slide(
            slide_path=slide_path,
            extractor=self.feature_extractor,
            model_config=self.model_config,
            tissue_mask_path=tissue_mask_path,
            num_workers_extraction=self.num_workers_extraction,
            quantize=self.quantize_extraction,
        )

        embeddings_tensor = torch.from_numpy(embeddings_np).float()
        patch_coords_tensor = torch.from_numpy(patch_coords_np).int() # Assuming coords are int

        # Apply label transform if provided, then convert to tensor
        if self.label_transform:
            transformed_label = self.label_transform(raw_label)
        else:
            # Default assumption: label is already numerical or can be directly converted
            try:
                transformed_label = int(raw_label) # Or float(raw_label) if regression
            except ValueError:
                logger.error(f"Could not convert label '{raw_label}' to int for slide {slide_path}. Consider using a label_transform.")
                raise
        
        # Assuming classification, so labels are long type.
        # For BCEWithLogitsLoss, labels might need to be float. This depends on the criterion.
        # For CrossEntropyLoss with N classes, labels should be Long and in [0, N-1].
        label_tensor = torch.tensor(transformed_label, dtype=torch.long) 

        if embeddings_tensor.ndim == 1 and embeddings_tensor.shape[0] == 0:
            # This happens if extract_features_for_slide returns empty arrays
            # due to no patches. We should return a 2D tensor (0, feature_dim).
            # The feature_dim can be obtained from the extractor if it has an embed_dim attribute.
            feature_dim = self.feature_extractor.embed_dim if hasattr(self.feature_extractor, 'embed_dim') else 0
            if feature_dim == 0 and hasattr(self.feature_extractor, '_model') and hasattr(self.feature_extractor._model, 'num_features'): # common in timm
                 feature_dim = self.feature_extractor._model.num_features

            logger.warning(f"Slide {slide_path} resulted in 0 patches. Returning empty embedding tensor of shape (0, {feature_dim}).")
            embeddings_tensor = torch.empty((0, feature_dim), dtype=torch.float32)
            patch_coords_tensor = torch.empty((0, 2), dtype=torch.int)


        return embeddings_tensor, label_tensor, patch_coords_tensor
