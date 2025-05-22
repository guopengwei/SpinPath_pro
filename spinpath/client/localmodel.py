"""API to load local models."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any, Literal, Sequence, Union

import jsonschema
import torch  # Added for type hinting

from spinpath.errors import InvalidModelConfiguration

ModelType = Literal["torchscript", "feature_extractor", "trainable_classifier"]


@dataclasses.dataclass
class ModelConfiguration:
    """Container for the configuration of a single model.

    This is from the contents of 'config.json'.
    """

    spec_version: str
    model_type: ModelType
    architecture_name: str
    patch_size_um: float  # Assuming this is relevant for all types for now
    # Optional fields, usage depends on model_type and architecture_name
    num_classes: int | None = None
    class_names: Sequence[str] | None = None
    feature_extractor: str | None = None  # Name of upstream feature extractor
    architecture_params: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.model_type == "trainable_classifier" or self.model_type == "torchscript":
            if self.num_classes is None or self.class_names is None:
                raise InvalidModelConfiguration(
                    f"'num_classes' and 'class_names' are required for model_type '{self.model_type}'"
                )
            if len(self.class_names) != self.num_classes:
                raise InvalidModelConfiguration(
                    f"Length of 'class_names' ({len(self.class_names)}) must match 'num_classes' ({self.num_classes})"
                )
        if self.model_type == "feature_extractor":
            if self.num_classes is not None or self.class_names is not None:
                # Or should we just ignore them? For now, let's be strict.
                raise InvalidModelConfiguration(
                    "'num_classes' and 'class_names' should not be set for model_type 'feature_extractor'"
                )


    @classmethod
    def from_dict(cls, config: dict) -> ModelConfiguration:
        validate_config_json(config)
        return cls(
            spec_version=config["spec_version"],
            model_type=config["model_type"],
            architecture_name=config["architecture_name"],
            patch_size_um=config["patch_size_um"],
            num_classes=config.get("num_classes"),
            class_names=config.get("class_names"),
            feature_extractor=config.get("feature_extractor"),
            architecture_params=config.get("architecture_params"),
        )


@dataclasses.dataclass
class Model:
    config: ModelConfiguration
    model_path: str | Path  # Path to model file (e.g. .pt, .pth) or directory
    model_instance: Union[torch.nn.Module, torch.jit.ScriptModule] | None = None # Loaded model instance

    def __post_init__(self) -> None:
        # For TorchScript, model_path must exist. For others, it might be a placeholder
        # if weights are downloaded or model is constructed without a single file.
        # This logic will be refined in loading functions.
        if self.config.model_type == "torchscript":
            if not Path(self.model_path).exists():
                raise FileNotFoundError(
                    f"Model file not found for TorchScript model: {self.model_path}"
                )


def validate_config_json(instance: object) -> bool:
    """Raise an error if the model configuration JSON is invalid. Otherwise return
    True.
    """
    schema_path = Path(__file__).parent / ".." / "schemas" / "model-config.schema.json"
    if not schema_path.exists():
        raise FileNotFoundError(
            f"JSON schema for model configurations not found: {schema_path}"
        )
    with open(schema_path) as f:
        schema = json.load(f)
    try:
        jsonschema.validate(instance, schema=schema)
    except jsonschema.ValidationError as e:
        raise InvalidModelConfiguration(
            "Invalid model configuration. See traceback above for details."
        ) from e

    return True


def load_torchscript_model_from_filesystem(
    model_path: str | Path, config_path: str | Path
) -> Model:
    """Load a model from local filesystem.
    
    This function now handles different model types based on ModelConfiguration.
    """
    with open(config_path) as f:
        config_dict = json.load(f)
    if not isinstance(config_dict, dict):
        raise TypeError(
            f"Expected configuration to be a dict but got {type(config_dict)}"
        )
    config = ModelConfiguration.from_dict(config_dict)

    model_instance: Union[torch.nn.Module, torch.jit.ScriptModule] | None = None

    if config.model_type == "torchscript":
        if not Path(model_path).exists() or not Path(model_path).is_file():
            raise FileNotFoundError(
                f"TorchScript model file not found or is not a file: {model_path}"
            )
        # Actual TorchScript loading would happen here, e.g.:
        # import torch
        # model_instance = torch.jit.load(model_path)
        # For now, we'll keep it conceptual as per subtask instructions
        # to focus on data structures first.
        pass  # Placeholder for actual loading
    elif config.model_type in ["feature_extractor", "trainable_classifier"]:
        # Loading logic for torch.nn.Module based models would go here.
        # This might involve:
        # 1. Constructing model from architecture_name and architecture_params
        #    (e.g., using a factory pattern or importing a class)
        # 2. Loading state_dict if model_path points to a .pth or .bin file.
        # For now, we'll keep it conceptual.
        if Path(model_path).exists() and Path(model_path).is_file():
            # This implies model_path is a state_dict or similar
            pass # Placeholder for state_dict loading
        elif Path(model_path).exists() and Path(model_path).is_dir():
            # This could imply model_path is a directory with model definition scripts
            # or multiple weight files. Deferring this complexity.
            pass
        # If model_path is not strictly required (e.g. using timm for a known feature extractor
        # without local files), this part needs careful handling.
        # The current Model.__post_init__ might be too strict.
        pass # Placeholder for actual loading

    # The model_instance would be assigned above.
    # For this subtask, we are focusing on the data structures, so actual model loading
    # is not implemented yet.
    model = Model(config=config, model_path=model_path, model_instance=model_instance)
    return model
