"""
Trainable models for SpinPath.
"""
from __future__ import annotations

from typing import Type
import torch

from .abmil import ABMIL
from .mamba2d import Mamba2DClassifier # Import the new Mamba2DClassifier

# This list is used to dynamically update help messages for the CLI.
__all__ = ["ABMIL", "Mamba2DClassifier"]

# Dictionary to map model names to their respective classes.
# This allows for loading models by name, similar to how extractors are handled.
TRAINABLE_MODELS: dict[str, Type[torch.nn.Module]] = {
    "ABMIL": ABMIL,
    "Mamba2DClassifier": Mamba2DClassifier, # Add Mamba2DClassifier to the dictionary
}

def list_trainable_models() -> list[str]:
    """List available trainable models."""
    return sorted(list(TRAINABLE_MODELS.keys()))

def get_trainable_model_class(name: str) -> Type[torch.nn.Module]:
    """
    Get a trainable model class by its name.

    Args:
        name: The name of the model (case-sensitive, e.g., "ABMIL").

    Returns:
        The model class.

    Raises:
        ValueError: If the model name is not found.
    """
    model_class = TRAINABLE_MODELS.get(name)
    if model_class is None:
        raise ValueError(
            f"Unknown trainable model: {name}. "
            f"Available models: {list_trainable_models()}"
        )
    return model_class

# Example of how to instantiate a model using this registry:
# model_name = "ABMIL"
# ModelClass = get_trainable_model_class(model_name)
# # These params would typically come from a config file or CLI args
# model_instance = ModelClass(input_dim=1024, hidden_dim=128, n_classes=2, dropout_rate=0.25)
#
# model_name_mamba = "Mamba2DClassifier"
# MambaModelClass = get_trainable_model_class(model_name_mamba)
# mamba_instance = MambaModelClass(input_dim=1024, d_model=128, n_layers=4, n_classes=2)

```
