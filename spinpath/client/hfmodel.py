"""API to interact with SpinPath models on HuggingFace Hub."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Union

import torch # Added for type hinting
from huggingface_hub import hf_hub_download

from spinpath.client.localmodel import Model
from spinpath.client.localmodel import ModelConfiguration
from spinpath.errors import InvalidModelConfiguration # Assuming this might be useful

HF_CONFIG_NAME = "config.json"
HF_TORCHSCRIPT_MODEL_NAME = "torchscript_model.pt" # Default name for TorchScript model
HF_PYTORCH_MODEL_NAME = "pytorch_model.bin" # Default name for PyTorch state_dict


@dataclasses.dataclass
class HFInfo:
    """Container for information on model's location on HuggingFace Hub."""

    repo_id: str
    revision: str | None = None
    # Potentially add downloaded_files list if multiple files are fetched.


@dataclasses.dataclass
class HFModel(Model):
    """Container for a model hosted on HuggingFace.
    
    Inherits 'config', 'model_path', and 'model_instance' from localmodel.Model.
    """

    hf_info: HFInfo
    # model_path will now point to the primary downloaded model file (e.g. .pt or .bin)
    # or potentially a directory if multiple components are downloaded.


def load_model_from_hf(
    repo_id: str, revision: str | None = None, custom_model_filename: str | None = None
) -> HFModel:
    """Load a model (TorchScript or PyTorch nn.Module) from HuggingFace Hub."""
    config_path = hf_hub_download(repo_id, HF_CONFIG_NAME, revision=revision)
    with open(config_path) as f:
        config_dict = json.load(f)
    if not isinstance(config_dict, dict):
        raise TypeError(
            f"Expected configuration to be a dict but got {type(config_dict)}"
        )
    config = ModelConfiguration.from_dict(config_dict)
    hf_info = HFInfo(repo_id=repo_id, revision=revision)

    model_instance: Union[torch.nn.Module, torch.jit.ScriptModule] | None = None
    downloaded_model_path: str | Path

    if config.model_type == "torchscript":
        model_filename = custom_model_filename or HF_TORCHSCRIPT_MODEL_NAME
        downloaded_model_path = hf_hub_download(repo_id, model_filename, revision=revision)
        # Actual TorchScript loading would happen here:
        # import torch
        # model_instance = torch.jit.load(downloaded_model_path)
        # For now, focusing on data structures.
        pass # Placeholder for actual loading

    elif config.model_type in ["feature_extractor", "trainable_classifier"]:
        # Determine the model weights filename. Could be a standard name or specified
        # in config.json (e.g., config.get("weights_file", HF_PYTORCH_MODEL_NAME))
        model_filename = custom_model_filename or config.architecture_params.get("weights_file", HF_PYTORCH_MODEL_NAME) if config.architecture_params else HF_PYTORCH_MODEL_NAME
        
        try:
            downloaded_model_path = hf_hub_download(repo_id, model_filename, revision=revision)
        except Exception as e: # Could be EntryNotFoundError if file doesn't exist
            # This might be acceptable if the model can be constructed without pre-trained weights
            # or if weights are optional (e.g. timm models that can be random init).
            # For now, let's assume weights are expected if model_type is not torchscript
            # and a file is attempted to be downloaded.
            # A more sophisticated check would be needed here.
            # If architecture_name allows construction without weights (e.g. via timm),
            # then downloaded_model_path might not be critical.
            # For this refactoring, we'll assume if a filename is determined, it should be loadable.
            raise FileNotFoundError(
                f"Failed to download model weights file '{model_filename}' from {repo_id}. Error: {e}"
            ) from e
            
        # Actual model construction and state_dict loading would happen here.
        # Example conceptual logic:
        # 1. Get architecture_name and architecture_params from config.
        # 2. if architecture_name in a known registry (e.g., timm, or a custom one):
        #    model_instance = build_model_from_registry(config.architecture_name, config.architecture_params)
        #    if Path(downloaded_model_path).exists():
        #        state_dict = torch.load(downloaded_model_path, map_location='cpu')
        #        model_instance.load_state_dict(state_dict)
        # For now, focusing on data structures.
        pass # Placeholder for actual loading
    else:
        raise InvalidModelConfiguration(f"Unsupported model_type '{config.model_type}' in config.json from {repo_id}")

    # model_path in HFModel will point to the downloaded primary model artifact.
    # If no specific file (e.g. timm model created without specific downloaded weights file),
    # config_path could be a stand-in, or it could be None / Path object to download dir.
    # For now, using downloaded_model_path.
    model = HFModel(
        config=config,
        model_path=downloaded_model_path, # This will be the path to the downloaded .pt or .bin file
        hf_info=hf_info,
        model_instance=model_instance # This would be populated by actual loading logic
    )
    return model
