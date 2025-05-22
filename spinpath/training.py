"""
Generic training module for SpinPath models.
"""
import logging
import time
from typing import Dict, Union, Optional, List

import torch
from torch.utils.data import DataLoader
from torch.optim.optimizer import Optimizer
# For older PyTorch versions, _LRScheduler might be in torch.optim.lr_scheduler.lr_scheduler
# For newer versions (1.11+), it's torch.optim.lr_scheduler.LRScheduler
# Using a more general approach for type hinting if _LRScheduler causes issues.
# from torch.optim.lr_scheduler import _LRScheduler # Pre PyTorch 1.11
try:
    from torch.optim.lr_scheduler import LRScheduler as LRSchedulerType
except ImportError:
    from torch.optim.lr_scheduler import _LRScheduler as LRSchedulerType


logger = logging.getLogger(__name__)
# Configure basic logging if no configuration is set by the application
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def train_model(
    model: torch.nn.Module,
    train_loader: DataLoader,
    criterion: torch.nn.Module,
    optimizer: Optimizer,
    num_epochs: int,
    device: Union[torch.device, str],
    val_loader: Optional[DataLoader] = None,
    lr_scheduler: Optional[LRSchedulerType] = None,
) -> Dict[str, List[float]]:
    """
    Trains a PyTorch model.

    Args:
        model: The model to be trained.
        train_loader: DataLoader for the training dataset.
                      Expected to yield batches of (inputs, labels).
                      - inputs: Tensor of input data.
                      - labels: Tensor of target labels.
                      Dataset-specifics (e.g. WSI patch loading, tile selection,
                      label generation from annotations) should be handled by the
                      Dataset class used within this DataLoader.
        criterion: The loss function.
        optimizer: The optimizer.
        num_epochs: Number of training epochs.
        device: The device to train on ('cuda', 'cpu', 'mps').
        val_loader: DataLoader for the validation dataset (optional).
                    Expected to yield batches of (inputs, labels) similar to train_loader.
        lr_scheduler: Learning rate scheduler (optional).

    Returns:
        A dictionary containing training history (e.g., 'train_loss', 'val_loss' per epoch).
    """
    if isinstance(device, str):
        device = torch.device(device)

    model.to(device)
    history: Dict[str, List[float]] = {"train_loss": [], "val_loss": []}

    logger.info(f"Starting training on device: {device}")

    for epoch in range(num_epochs):
        epoch_start_time = time.time()
        model.train()
        running_train_loss = 0.0
        train_batches = 0

        for i, batch_data in enumerate(train_loader):
            # Assuming batch_data is a tuple or list: (inputs, labels)
            # Specific unpacking might be needed if DataLoader yields more complex structures.
            try:
                inputs, labels = batch_data
            except ValueError:
                logger.error(
                    "Failed to unpack batch_data. Expected (inputs, labels). "
                    "Ensure your DataLoader yields data in this format."
                )
                # Potentially raise an error or skip batch
                raise ValueError("train_loader did not yield (inputs, labels)")

            inputs, labels = inputs.to(device), labels.to(device)

            optimizer.zero_grad()
            outputs = model(inputs) # Forward pass
            loss = criterion(outputs, labels)
            loss.backward() # Backward pass
            optimizer.step() # Optimize

            running_train_loss += loss.item() * inputs.size(0) # Weighted by batch size
            train_batches += inputs.size(0)

            # Log every N batches, e.g., 100 or based on dataset size
            log_interval = 100
            if (i + 1) % log_interval == 0 or (i + 1) == len(train_loader):
                current_avg_loss = running_train_loss / train_batches if train_batches > 0 else 0
                logger.info(
                    f"[Epoch {epoch+1}/{num_epochs}, Batch {i+1}/{len(train_loader)}] "
                    f"Training loss: {current_avg_loss:.4f}"
                )
        
        epoch_train_loss = running_train_loss / train_batches if train_batches > 0 else 0.0
        history["train_loss"].append(epoch_train_loss)
        logger.info(f"Epoch {epoch+1}/{num_epochs} Training Loss: {epoch_train_loss:.4f}")

        if val_loader:
            model.eval()
            running_val_loss = 0.0
            val_batches = 0
            with torch.no_grad():
                for inputs_val, labels_val in val_loader:
                    inputs_val, labels_val = inputs_val.to(device), labels_val.to(device)
                    outputs_val = model(inputs_val)
                    val_loss = criterion(outputs_val, labels_val)
                    running_val_loss += val_loss.item() * inputs_val.size(0) # Weighted by batch size
                    val_batches += inputs_val.size(0)
            
            epoch_val_loss = running_val_loss / val_batches if val_batches > 0 else 0.0
            history["val_loss"].append(epoch_val_loss)
            logger.info(f"Epoch {epoch+1}/{num_epochs} Validation Loss: {epoch_val_loss:.4f}")

            if lr_scheduler:
                # Some schedulers like ReduceLROnPlateau need the validation metric
                if isinstance(lr_scheduler, torch.optim.lr_scheduler.ReduceLROnPlateau):
                    lr_scheduler.step(epoch_val_loss)
                else:
                    lr_scheduler.step()
        elif lr_scheduler: # If no val_loader but lr_scheduler exists
             # Ensure schedulers not dependent on validation metric can still step
            if not isinstance(lr_scheduler, torch.optim.lr_scheduler.ReduceLROnPlateau):
                lr_scheduler.step()
            else:
                logger.warning(
                    "ReduceLROnPlateau scheduler provided without a validation loader. "
                    "Scheduler will not step."
                )
        
        epoch_duration = time.time() - epoch_start_time
        logger.info(f"Epoch {epoch+1}/{num_epochs} completed in {epoch_duration:.2f}s.")


    logger.info("Training finished.")
    return history

# Example of how a Dataset for WSI data might be structured (conceptual):
#
# from torch.utils.data import Dataset
# class WSIDataset(Dataset):
#     def __init__(self, wsis: List[Path], labels_df, transform=None, patch_size=256, level=0):
#         self.wsis = wsis  # List of paths to WSI files
#         self.labels_df = labels_df # DataFrame with WSI IDs and corresponding labels
#         self.transform = transform
#         self.patch_size = patch_size
#         self.level = level
#         # Pre-calculate patch coordinates or determine them on-the-fly
#         self._patch_info = self._generate_patch_info()
#
#     def _generate_patch_info(self):
#         patch_info = []
#         # For each WSI:
#         # 1. Open WSI (e.g., using OpenSlide).
#         # 2. Perform tissue segmentation (optional, to focus on relevant areas).
#         # 3. Generate patch coordinates from tissue regions or entire WSI.
#         # 4. Associate patches with WSI-level labels.
#         # Each element in patch_info could be (wsi_path, x, y, label)
#         # This is a complex step involving WSI processing libraries.
#         # For MIL, you might load all patches for a WSI (a "bag") or sample patches.
#         # For patch-level classifiers, each patch is an item.
#         # Example: patch_info.append({'wsi_id': 'slide001', 'x': 1000, 'y': 2000, 'label': 0})
#         return patch_info
#
#     def __len__(self):
#         return len(self._patch_info)
#
#     def __getitem__(self, idx):
#         info = self._patch_info[idx]
#         # 1. Open WSI corresponding to info['wsi_id']
#         # 2. Read region at (info['x'], info['y']) with size (patch_size, patch_size) at self.level
#         #    wsi = openslide.OpenSlide(info['wsi_path'])
#         #    patch = wsi.read_region((info['x'], info['y']), self.level, (self.patch_size, self.patch_size))
#         #    patch_rgb = patch.convert("RGB")
#         # 3. Convert to PyTorch tensor
#         #    patch_tensor = ToTensor()(patch_rgb) # from torchvision.transforms
#         # 4. Apply transforms if any
#         #    if self.transform:
#         #        patch_tensor = self.transform(patch_tensor)
#         # 5. Return patch tensor and its label
#         #    label = torch.tensor(info['label'], dtype=torch.long) # Or float for regression
#         # return patch_tensor, label
#         pass # Placeholder
#
# Conceptual DataLoader usage:
# train_dataset = WSIDataset(...)
# train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True, num_workers=4)
#
# val_dataset = WSIDataset(...)
# val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False, num_workers=4)
```
