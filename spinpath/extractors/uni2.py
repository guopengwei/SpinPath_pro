"""UNI2 feature extractor."""

import timm
import torch
from timm.data import resolve_data_config # Corrected: Removed model from resolve_data_config args
from timm.data.transforms_factory import create_transform
from torchvision.transforms import Compose

from .base import PatchFeatureExtractor


class UNI2(PatchFeatureExtractor):
    """UNI2 feature extractor.

    Model from https://huggingface.co/MahmoodLab/UNI2-h
    """

    @property
    def name(self) -> str:
        return "UNI2"

    def load_model(self) -> torch.nn.Module:
        """Load the UNI2 model from HuggingFace Hub using timm."""
        try:
            # As per timm documentation and common usage for HF models:
            # pretrained=True is implicit when loading a hf-hub model.
            # num_classes=0 is often used for feature extraction to get the penultimate layer features.
            # However, UNI2 is a vision transformer, its feature extraction might be via forward_features
            # or a specific attribute. For now, load the model as is and assume timm handles
            # feature extraction correctly or that the default forward pass gives features.
            # If specific feature extraction methods are needed, this might need adjustment.
            # The model card doesn't specify particular timm args beyond the model name.
            model = timm.create_model(
                "hf-hub:MahmoodLab/UNI2-h",
                pretrained=True, 
                num_classes=0 # Standard practice for feature extraction with timm
            )
        except Exception as e:
            # Provide more context in case of loading failure
            raise RuntimeError(
                f"Failed to load model 'hf-hub:MahmoodLab/UNI2-h' from timm. "
                f"Ensure you have an internet connection and the model name is correct. Error: {e}"
            ) from e

        assert isinstance(model, torch.nn.Module), \
            f"Expected timm.create_model to return a torch.nn.Module, but got {type(model)}"
        
        model = model.eval().to(self.device)
        return model

    @property
    def transform(self) -> Compose:
        """Get the preprocessing transform for the UNI2 model."""
        # Ensure model is loaded before creating transforms based on its config
        if self._model is None:
            # This should ideally not happen if used correctly,
            # as PatchFeatureExtractor.__init__ calls self.load_model()
            # which initializes self._model
            raise RuntimeError("Model not loaded. Cannot create transform.")

        # For timm versions where model.pretrained_cfg might not exist or be preferred,
        # directly passing model_name to resolve_data_config might be an option.
        # However, the example uses self.model.pretrained_cfg.
        # If self.model (which is _model) is guaranteed to be populated, this is fine.
        try:
            # The model instance itself is passed to resolve_data_config,
            # which then accesses model.pretrained_cfg or model.default_cfg
            data_config = resolve_data_config(model=self._model) # Pass the model instance
            transform = create_transform(**data_config)
        except Exception as e:
            # Provide more context in case of transform creation failure
            raise RuntimeError(
                f"Failed to create transform for model '{self.name}'. "
                f"Ensure the model's pretrained_cfg is valid. Error: {e}"
            ) from e
            
        assert isinstance(transform, Compose), \
            f"Expected create_transform to return a torchvision.transforms.Compose, but got {type(transform)}"
        return transform