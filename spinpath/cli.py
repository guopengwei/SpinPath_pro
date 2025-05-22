"""Command line interface for SpinPath."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import click
from PIL import Image

from spinpath.client.hfmodel import load_torchscript_model_from_hf
import json # For loading model config
import torch
import torch.optim as optim
import torch.nn as nn

from spinpath.client.localmodel import Model, ModelConfiguration # ModelConfiguration needed
from spinpath.client.localmodel import load_torchscript_model_from_filesystem
from spinpath.inference import infer_one_slide
# Adjust imports based on actual __init__ structure
from spinpath.extractors import EXTRACTORS as _EXTRACTORS_DICT # Use the actual dict
from spinpath.extractors import get_extractor_by_name as get_extractor_class # Use the actual function
from spinpath.trainable_models import list_trainable_models, get_trainable_model_class
from spinpath.training import train_model
from spinpath.data import WSITrainingDataset # Added
from torch.utils.data import DataLoader # Added

logger = logging.getLogger(__name__)

# Basic logging configuration if not already set by the application
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Helper to get available device
def get_default_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    # Add MPS support if desired and PyTorch version supports it well
    # elif torch.backends.mps.is_available() and torch.backends.mps.is_built():
    #     return "mps" 
    return "cpu"


def _load_tissue_mask(path: str | Path) -> Image.Image:
    logger.info(f"Loading tissue mask: {path}")
    with Image.open(path) as tissue_mask:
        tissue_mask.load()
    if tissue_mask.mode != "1":
        logger.info(
            f"Converting tissue mask from mode '{tissue_mask.mode}' to mode '1'"
        )
        tissue_mask = tissue_mask.convert("1")
    return tissue_mask


def _run_impl(
    wsi_path: Path,
    model: Model,
    tissue_mask_path: Path | None,
    num_workers: int,
    tablefmt: str,
    json: bool,
    quantize: bool,
) -> None:
    tissue_mask: Image.Image | None = None
    if tissue_mask_path is not None:
        tissue_mask = _load_tissue_mask(tissue_mask_path)

    result = infer_one_slide(
        slide_path=wsi_path,
        model=model,
        tissue_mask=tissue_mask,
        num_workers=num_workers,
        quantize=quantize,
    )

    if json:
        click.echo(result.to_json(fp=None))
    else:
        click.echo(result.to_str_table(tablefmt=tablefmt))


@click.group()
def cli() -> None:
    """Run specimen-level inference or train models using SpinPath."""


@cli.command("run") # Explicitly naming the command
@click.option(
    "-m", "--hf-repo-id", required=True, help="HuggingFace Hub repo ID of the model"
)
@click.option(
    "-i",
    "--wsi-path",
    required=True,
    help="Path to the whole slide image",
    type=click.Path(exists=True, path_type=Path),
)
@click.option(
    "--hf-repo-revision", help="Revision of the HuggingFace Hub repo", default=None
)
@click.option(
    "--tissue-mask-path",
    help="Path to the tissue mask for this image",
    type=click.Path(exists=True, path_type=Path),
    default=None,
)
@click.option(
    "-j",
    "--num-workers",
    help="Number of workers to use during patch feature extraction. -1 (default) uses"
    " all cores.",
    type=click.IntRange(min=-1, max=os.cpu_count()),
    default=-1,
    show_default=True,
)
@click.option(
    "--table-format",
    help="Format of the output table with results. See Python Tabulate for a list of"
    " options.",
)
@click.option(
    "--json", is_flag=True, help="Print the model outputs (and attention) as JSON"
)
@click.option("--quantize", is_flag=True, help="Quantize embedding model to float16")
def run(
    *,
    hf_repo_id: str,
    wsi_path: Path,
    hf_repo_revision: str | None,
    tissue_mask_path: Path | None,
    num_workers: int,
    table_format: str,
    json: bool,
    quantize: bool,
) -> None:
    model = load_torchscript_model_from_hf(hf_repo_id, hf_repo_revision)
    if num_workers == -1:
        num_workers = os.cpu_count() or 0
    _run_impl(
        wsi_path=wsi_path,
        model=model,
        tissue_mask_path=tissue_mask_path,
        num_workers=num_workers,
        tablefmt=table_format,
        json=json,
        quantize=quantize,
    )


@cli.command("runlocal") # Explicitly naming the command
@click.option("-m", "--model-path", help="Path to a TorchScript model", type=click.Path(exists=True, path_type=Path))
@click.option("-c", "--model-config-path", help="Path to a JSON model config", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-i",
    "--wsi-path",
    help="Path to the whole slide image",
    type=click.Path(exists=True, path_type=Path),
)
@click.option(
    "--tissue-mask-path",
    help="Path to the tissue mask for this image",
    type=click.Path(exists=True, path_type=Path),
    default=None,
)
@click.option(
    "-j",
    "--num-workers",
    help="Number of workers to use during patch feature extraction",
    type=click.IntRange(min=0, max=os.cpu_count()),
    default=4,
    show_default=True,
)
@click.option(
    "--table-format",
    help="Format of the output table with results. See Python Tabulate for a list of"
    " options.",
)
@click.option(
    "--json", is_flag=True, help="Print the model outputs (and attention) as JSON"
)
@click.option("--quantize", is_flag=True, help="Quantize embedding model to float16")
def runlocal(
    *,
    model_path: Path,
    model_config_path: Path,
    wsi_path: Path,
    tissue_mask_path: Path | None,
    num_workers: int,
    table_format: str,
    json: bool,
    quantize: bool,
) -> None:
    model = load_torchscript_model_from_filesystem(model_path, model_config_path)
    _run_impl(
        wsi_path=wsi_path,
        model=model,
        tissue_mask_path=tissue_mask_path,
        num_workers=num_workers,
        tablefmt=table_format,
        json=json,
        quantize=quantize,
    )


@cli.command("train")
@click.option(
    "--dataset-csv",
    type=click.Path(exists=True, path_type=Path, dir_okay=False),
    required=True,
    help="Path to dataset CSV file (columns: slide_path, label, optional: mask_path).",
)
@click.option(
    "--model-name",
    type=click.Choice(list_trainable_models()),
    required=True,
    help="Name of the trainable model.",
)
@click.option(
    "--feature-extractor-name",
    type=click.Choice(list(_EXTRACTORS_DICT.keys())), # Use the actual dict keys
    required=True,
    help="Name of the feature extractor for tile featurization.",
)
@click.option(
    "--model-config-path",
    type=click.Path(exists=True, path_type=Path, dir_okay=False),
    required=True,
    help="Path to the model JSON configuration file (defines model_type, architecture_name, architecture_params etc.).",
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    required=True,
    help="Directory to save training outputs (model checkpoints, logs, etc.).",
)
@click.option(
    "--num-epochs",
    type=int,
    default=10,
    show_default=True,
    help="Number of training epochs.",
)
@click.option(
    "--learning-rate",
    type=float,
    default=1e-4,
    show_default=True,
    help="Initial learning rate.",
)
@click.option(
    "--batch-size",
    type=int,
    default=1, # MIL typically uses batch_size=1 as each "batch" is a bag of instances
    show_default=True,
    help="Batch size (number of bags per iteration).",
)
@click.option(
    "--optimizer-name",
    type=click.Choice(["Adam", "SGD", "AdamW"]),
    default="Adam",
    show_default=True,
    help="Name of the optimizer.",
)
@click.option(
    "--loss-function",
    type=click.Choice(["CrossEntropyLoss", "BCEWithLogitsLoss"]),
    default="CrossEntropyLoss",
    show_default=True,
    help="Name of the loss function.",
)
@click.option(
    "--lr-scheduler-name",
    type=click.Choice(["StepLR", "ReduceLROnPlateau"]),
    default=None, # Optional
    show_default=True,
    help="Name of the learning rate scheduler (optional).",
)
@click.option(
    "--num-workers",
    type=int,
    default=4,
    show_default=True,
    help="Number of workers for data loading.",
)
@click.option(
    "--device",
    type=str,
    default=get_default_device(), # Dynamically set default
    show_default=True,
    help="Device to use for training ('cuda', 'cpu', 'mps').",
)
@click.option(
    "--seed",
    type=int,
    default=None,
    help="Random seed for reproducibility (optional).",
)
@click.option(
    "--create-output-dir",
    is_flag=True,
    help="If set, create the output directory if it doesn't exist.",
)
def train(
    dataset_csv: Path,
    model_name: str,
    feature_extractor_name: str,
    model_config_path: Path,
    output_dir: Path,
    num_epochs: int,
    learning_rate: float,
    batch_size: int,
    optimizer_name: str,
    loss_function: str,
    lr_scheduler_name: str | None,
    num_workers: int,
    device: str,
    seed: int | None,
    create_output_dir: bool,
):
    """Train a new model using extracted features."""
    
    main_params = {
        "dataset_csv": dataset_csv, "model_name": model_name, 
        "feature_extractor_name": feature_extractor_name, "model_config_path": model_config_path,
        "output_dir": output_dir, "num_epochs": num_epochs, "learning_rate": learning_rate,
        "batch_size": batch_size, "optimizer_name": optimizer_name, "loss_function": loss_function,
        "lr_scheduler_name": lr_scheduler_name, "num_workers": num_workers, "device": device,
        "seed": seed, "create_output_dir": create_output_dir,
    }
    logger.info("Starting 'train' command with parameters:")
    for key, value in main_params.items():
        logger.info(f"  {key}: {value}")

    if create_output_dir:
        logger.info(f"Attempting to create output directory: {output_dir}")
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Output directory ensured: {output_dir}")

    if seed is not None:
        logger.info(f"Setting random seed to: {seed}")
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        # Potentially add numpy and random seeds here too for full reproducibility
        # import numpy as np
        # import random
        # np.random.seed(seed)
        # random.seed(seed)

    # Determine device
    actual_device = torch.device(device)
    logger.info(f"Using device: {actual_device}")

    # Load ModelConfiguration from model_config_path
    logger.info(f"Loading model configuration from: {model_config_path}")
    try:
        with open(model_config_path, 'r') as f:
            config_json = json.load(f)
        # Assuming ModelConfiguration has from_dict or similar method
        # and that the JSON directly matches ModelConfiguration structure
        # This part was refactored in a previous subtask.
        model_config = ModelConfiguration.from_dict(config_json)
        logger.info(f"Model configuration loaded successfully: {model_config}")
    except Exception as e:
        logger.error(f"Failed to load or parse model configuration: {e}")
        raise click.Abort()

    # Placeholder: Instantiate feature extractor
    logger.info(f"Placeholder: Initializing feature extractor: {feature_extractor_name}")
    # extractor_class = get_extractor_class(feature_extractor_name) # get_extractor_class is an alias for get_extractor_by_name
    # extractor_instance = extractor_class(device=actual_device) # Or other params as needed
    logger.info(f"Initializing feature extractor: {feature_extractor_name}")
    try:
        extractor_constructor = get_extractor_class(feature_extractor_name)
        # The extractor's device should be the same as the training device
        # Quantize option from CLI is for feature extraction if done on the fly or for caching
        # For now, the extractor instance is created, and its internal device will be set.
        # The `extract_features_for_slide` will use the device set within the extractor.
        # The `PatchFeatureExtractor` base class sets `self.device` in its constructor.
        feature_extractor_instance = extractor_constructor(device=actual_device)
        logger.info(f"Feature extractor '{feature_extractor_name}' initialized on device '{feature_extractor_instance.device}'.")
    except Exception as e:
        logger.error(f"Failed to initialize feature extractor '{feature_extractor_name}': {e}")
        raise click.Abort()

    # Determine extractor's output dimension for the trainable model's input_dim
    # This is a crucial step. For now, using a placeholder.
    # A more robust way would be to have an `embed_dim` property on the extractor.
    try:
        # Attempt to get embed_dim from extractor, or a common attribute like _model.num_features
        if hasattr(feature_extractor_instance, 'embed_dim') and feature_extractor_instance.embed_dim > 0:
             EXTRACTOR_OUTPUT_DIM = feature_extractor_instance.embed_dim
        elif hasattr(feature_extractor_instance, '_model') and hasattr(feature_extractor_instance._model, 'num_features'): # common in timm
             EXTRACTOR_OUTPUT_DIM = feature_extractor_instance._model.num_features
        else:
            # Fallback or raise error if not determinable
            # For now, logging a warning and using a common default, but this should be configured.
            EXTRACTOR_OUTPUT_DIM = 1024 # Default placeholder if not found
            logger.warning(f"Could not automatically determine embed_dim for {feature_extractor_name}. Using default: {EXTRACTOR_OUTPUT_DIM}. This should be configured correctly.")
        logger.info(f"Determined extractor output dimension: {EXTRACTOR_OUTPUT_DIM}")
    except Exception as e:
        logger.error(f"Error determining feature extractor output dimension: {e}")
        raise click.Abort()


    # Instantiate trainable model
    logger.info(f"Initializing trainable model: {model_name}")
    try:
        model_class = get_trainable_model_class(model_name)
        arch_params = model_config.architecture_params if model_config.architecture_params is not None else {}
        
        if model_config.num_classes is None:
            logger.error("model_config.num_classes is not set. Cannot initialize model.")
            raise InvalidModelConfiguration("num_classes must be set in model_config for trainable models.") # Assuming InvalidModelConfiguration is imported or defined
        
        trainable_model = model_class(
            input_dim=EXTRACTOR_OUTPUT_DIM, 
            n_classes=model_config.num_classes, 
            **arch_params
        ).to(actual_device)
        logger.info(f"Trainable model '{model_name}' initialized with input_dim={EXTRACTOR_OUTPUT_DIM}, n_classes={model_config.num_classes}, architecture_params={arch_params}.")
    except Exception as e:
        logger.error(f"Failed to initialize trainable model '{model_name}': {e}")
        raise click.Abort()

    # Instantiate optimizer
    logger.info(f"Initializing optimizer: {optimizer_name} with LR: {learning_rate}")
    # if optimizer_name == "Adam":
    #     optimizer_instance = optim.Adam(trainable_model.parameters(), lr=learning_rate)
    # elif optimizer_name == "SGD":
    #     optimizer_instance = optim.SGD(trainable_model.parameters(), lr=learning_rate)
    # elif optimizer_name == "AdamW":
    #     optimizer_instance = optim.AdamW(trainable_model.parameters(), lr=learning_rate)
    # else: # Should not happen due to click.Choice
    try:
        if optimizer_name == "Adam":
            optimizer_instance = optim.Adam(trainable_model.parameters(), lr=learning_rate)
        elif optimizer_name == "SGD":
            optimizer_instance = optim.SGD(trainable_model.parameters(), lr=learning_rate)
        elif optimizer_name == "AdamW":
            optimizer_instance = optim.AdamW(trainable_model.parameters(), lr=learning_rate)
        else: # Should not happen due to click.Choice
            logger.error(f"Unsupported optimizer: {optimizer_name}")
            raise click.Abort() # Should not be reached
        logger.info(f"Optimizer '{optimizer_name}' initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize optimizer '{optimizer_name}': {e}")
        raise click.Abort()

    # Instantiate loss function
    logger.info(f"Initializing loss function: {loss_function}")
    try:
        if loss_function == "CrossEntropyLoss":
            criterion_instance = nn.CrossEntropyLoss()
        elif loss_function == "BCEWithLogitsLoss":
            criterion_instance = nn.BCEWithLogitsLoss()
        else: # Should not happen
            logger.error(f"Unsupported loss function: {loss_function}")
            raise click.Abort() # Should not be reached
        logger.info(f"Loss function '{loss_function}' initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize loss function '{loss_function}': {e}")
        raise click.Abort()
    
    # Instantiate LR scheduler
    lr_scheduler_instance = None
    if lr_scheduler_name:
        logger.info(f"Initializing LR scheduler: {lr_scheduler_name}")
        try:
            if lr_scheduler_name == "StepLR":
                # Example params, consider making these configurable
                lr_scheduler_instance = optim.lr_scheduler.StepLR(optimizer_instance, step_size=30, gamma=0.1)
            elif lr_scheduler_name == "ReduceLROnPlateau":
                # Example params, consider making these configurable
                lr_scheduler_instance = optim.lr_scheduler.ReduceLROnPlateau(optimizer_instance, mode='min', factor=0.1, patience=10)
            logger.info(f"LR Scheduler '{lr_scheduler_name}' initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize LR scheduler '{lr_scheduler_name}': {e}")
            # Decide if this is a fatal error or if training can proceed without scheduler
            logger.warning(f"Proceeding without LR scheduler due to initialization error.")
            lr_scheduler_instance = None # Ensure it's None if failed
    else:
        logger.info("No LR scheduler specified.")

    # Instantiate WSITrainingDataset
    logger.info("Initializing training dataset...")
    try:
        # quantize_extraction can be passed from CLI if added as an option, True/False
        # For now, let's assume it's False or passed as a fixed value.
        # Let's use the main 'quantize' flag from the run/runlocal commands for now,
        # or add a specific --quantize-extraction flag to train command.
        # For this step, let's assume a new CLI option --quantize-extraction was added
        # and is available as `quantize_extraction_cli_arg`.
        # If not, default to False for now.
        quantize_extraction_cli_arg = False # Placeholder: add this as a click option if needed
        
        train_dataset = WSITrainingDataset(
            dataset_csv_path=dataset_csv,
            feature_extractor=feature_extractor_instance,
            model_config=model_config, # Loaded ModelConfiguration
            num_workers_extraction=num_workers, # From CLI --num-workers
            quantize_extraction=quantize_extraction_cli_arg, # Placeholder
            label_transform=lambda x: int(x) # Basic transform, assumes labels are convertible to int
        )
        logger.info(f"Training dataset initialized with {len(train_dataset)} samples.")
    except Exception as e:
        logger.error(f"Failed to initialize training dataset: {e}")
        raise click.Abort()

    # Instantiate DataLoader
    # For MIL, batch_size is often 1 (each "item" is a bag).
    # If batch_size > 1, a custom collate_fn would be needed to handle bags of varying sizes.
    # The current WSITrainingDataset.__getitem__ returns (embeddings_tensor, label_tensor, patch_coords_tensor).
    # Default collate should work for batch_size=1.
    logger.info(f"Initializing training DataLoader with batch_size: {batch_size} and num_workers: {num_workers}")
    if batch_size > 1:
        logger.warning(f"Batch size {batch_size} > 1 for MIL. Ensure your model and collate_fn (if any) handle batches of bags. Using default collate for now.")
    
    try:
        train_loader = DataLoader(
            train_dataset,
            batch_size=batch_size, # From CLI
            shuffle=True, # Shuffle slides for training
            num_workers=0, # IMPORTANT: DataLoader num_workers should be 0 if dataset.__getitem__ is heavy (like feature extraction)
                           # The num_workers_extraction in WSITrainingDataset handles parallelism for feature extraction.
                           # Using >0 workers here would mean multiple slides are processed by __getitem__ in parallel,
                           # each potentially spawning its own set of num_workers_extraction. This can lead to resource over-subscription.
                           # Set to 0 to process one slide at a time sequentially at the DataLoader level.
            # collate_fn=None # Default collate should work for batch_size=1
        )
        logger.info("Training DataLoader initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize training DataLoader: {e}")
        raise click.Abort()
    
    # Placeholder for validation loader - assuming no validation split for now
    val_loader = None
    logger.info("Validation loader is not implemented in this step (set to None).")


    logger.info("Starting training...")
    try:
        history = train_model(
            model=trainable_model,
            train_loader=train_loader, # Now using the actual DataLoader
            criterion=criterion_instance, 
            optimizer=optimizer_instance, 
            num_epochs=num_epochs,
            device=actual_device,
            val_loader=val_loader, # Still None for now
            lr_scheduler=lr_scheduler_instance 
        )
        logger.info(f"Training completed. History: {history}")
    except Exception as e:
        logger.error(f"An error occurred during model training: {e}")
        # Potentially save a checkpoint or partial results here
        raise click.Abort()

    logger.info("Saving model...")
    try:
        model_save_path = output_dir / f"{model_name}_final.pth"
        torch.save(trainable_model.state_dict(), model_save_path)
        logger.info(f"Trained model state_dict saved to {model_save_path}")
        
        # Also save model_config.json to output_dir
        final_config_path = output_dir / "model_config.json"
        with open(final_config_path, 'w') as f_out:
           json.dump(config_json, f_out, indent=4) # Save the original loaded config (which was validated by ModelConfiguration)
        logger.info(f"Model configuration used for training saved to {final_config_path}")
    except Exception as e:
        logger.error(f"Failed to save model or configuration: {e}")
        # Not aborting here as training is complete, but user should be warned.

    click.echo(f"Training finished. Model and configuration saved to {output_dir}.")
