import unittest
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from torch.optim import Adam
from typing import Dict, List

# Assuming spinpath is in PYTHONPATH
from spinpath.training import train_model

# Dummy components for testing train_model
class DummyDataset(Dataset):
    def __init__(self, num_samples=20, feature_dim=64, num_classes=2, is_mil=True):
        self.num_samples = num_samples
        self.feature_dim = feature_dim
        self.num_classes = num_classes
        self.is_mil = is_mil # If true, each sample is a "bag" of instances

        if self.is_mil:
            # For MIL, each sample is a bag of varying number of instances
            # For simplicity in dummy dataset, let's make it fixed for now
            self.num_instances_per_bag = 10 
            self.data = [torch.randn(self.num_instances_per_bag, feature_dim) for _ in range(num_samples)]
        else:
            # For non-MIL, each sample is a single instance
            self.data = [torch.randn(feature_dim) for _ in range(num_samples)]
        
        self.labels = [torch.randint(0, num_classes, (1,)).squeeze() for _ in range(num_samples)]

    def __len__(self):
        return self.num_samples

    def __getitem__(self, idx):
        # For MIL, train_model expects (bag_features, label_tensor)
        # For non-MIL, it's (instance_feature, label_tensor)
        return self.data[idx], self.labels[idx]

class DummyMILModel(nn.Module):
    def __init__(self, input_dim, n_classes):
        super().__init__()
        # For MIL, input is (batch_size=1, num_instances, input_dim)
        # We need to aggregate instance features. Simple mean pooling for dummy.
        self.fc = nn.Linear(input_dim, n_classes)

    def forward(self, x):
        # x shape: (batch_size, num_instances, input_dim) if collate_fn handles it,
        # or (num_instances, input_dim) if batch_size=1 and no collate_fn.
        # train_model passes (inputs, labels) where inputs is from DataLoader.
        # If batch_size=1 from DataLoader, x will be (1, num_instances, input_dim)
        # if default collate stacks it, or (num_instances, input_dim) if not.
        # Let's assume default collate for batch_size=1 results in (1, num_instances, input_dim)
        # or if input is already batched by a custom collate fn.

        if x.ndim == 3: # (batch_size, num_instances, feature_dim)
            x = torch.mean(x, dim=1) # Aggregate instances: (batch_size, feature_dim)
        # If x.ndim == 2 (single bag, num_instances, feature_dim), no aggregation needed here
        # as it's already a single bag representation if the model expects that.
        # However, our DummyDataset provides (num_instances, feature_dim) per getitem.
        # Default collate for batch_size=1 will make it (1, num_instances, feature_dim).
        return self.fc(x)

class DummyNonMILModel(nn.Module):
    def __init__(self, input_dim, n_classes):
        super().__init__()
        self.fc = nn.Linear(input_dim, n_classes)

    def forward(self, x):
        # x shape: (batch_size, input_dim)
        return self.fc(x)


class TestTrainingModule(unittest.TestCase):

    def test_train_model_mil_case(self):
        """Test train_model with a dummy MIL dataset and model."""
        feature_dim = 64
        n_classes = 2
        device = torch.device("cpu")

        # MIL specific setup
        dummy_mil_dataset = DummyDataset(num_samples=4, feature_dim=feature_dim, num_classes=n_classes, is_mil=True)
        # For MIL, batch_size=1 is common. Default collate will add a batch dimension.
        # So, input to model will be (1, num_instances_per_bag, feature_dim)
        dummy_mil_loader = DataLoader(dummy_mil_dataset, batch_size=1, shuffle=True)
        
        dummy_mil_model = DummyMILModel(input_dim=feature_dim, n_classes=n_classes).to(device)
        optimizer = Adam(dummy_mil_model.parameters(), lr=1e-3)
        criterion = nn.CrossEntropyLoss() # Suitable for multi-class

        history = train_model(
            model=dummy_mil_model,
            train_loader=dummy_mil_loader,
            criterion=criterion,
            optimizer=optimizer,
            num_epochs=2,
            device=device,
            val_loader=None, # No validation for this basic test
            lr_scheduler=None
        )

        self.assertIsInstance(history, Dict)
        self.assertIn("train_loss", history)
        self.assertIsInstance(history["train_loss"], List)
        self.assertEqual(len(history["train_loss"]), 2) # 2 epochs
        for loss in history["train_loss"]:
            self.assertIsInstance(loss, float)
        
        # Check val_loss is empty if no val_loader
        self.assertIn("val_loss", history)
        self.assertEqual(len(history["val_loss"]), 0)


    def test_train_model_non_mil_case_with_validation(self):
        """Test train_model with a dummy non-MIL dataset, model, and validation."""
        feature_dim = 32
        n_classes = 2 # For BCEWithLogitsLoss, often n_classes=1 for binary
        device = torch.device("cpu")

        # Non-MIL setup
        dummy_train_dataset = DummyDataset(num_samples=6, feature_dim=feature_dim, num_classes=n_classes, is_mil=False)
        dummy_val_dataset = DummyDataset(num_samples=3, feature_dim=feature_dim, num_classes=n_classes, is_mil=False)

        # For non-MIL, batch_size can be > 1
        dummy_train_loader = DataLoader(dummy_train_dataset, batch_size=2, shuffle=True)
        dummy_val_loader = DataLoader(dummy_val_dataset, batch_size=2)
        
        dummy_model = DummyNonMILModel(input_dim=feature_dim, n_classes=n_classes).to(device)
        optimizer = Adam(dummy_model.parameters(), lr=1e-3)
        
        # If n_classes=1 for binary, use BCEWithLogitsLoss and labels should be float.
        # If n_classes=2 for binary, use CrossEntropyLoss and labels are long.
        # Our dummy dataset gives long labels.
        criterion = nn.CrossEntropyLoss()
        
        # Dummy LR Scheduler
        lr_scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=1, gamma=0.9)


        history = train_model(
            model=dummy_model,
            train_loader=dummy_train_loader,
            criterion=criterion,
            optimizer=optimizer,
            num_epochs=1,
            device=device,
            val_loader=dummy_val_loader,
            lr_scheduler=lr_scheduler
        )

        self.assertIsInstance(history, Dict)
        self.assertIn("train_loss", history)
        self.assertIsInstance(history["train_loss"], List)
        self.assertEqual(len(history["train_loss"]), 1)
        self.assertIn("val_loss", history)
        self.assertIsInstance(history["val_loss"], List)
        self.assertEqual(len(history["val_loss"]), 1)
        for loss_type in ["train_loss", "val_loss"]:
            for loss in history[loss_type]:
                self.assertIsInstance(loss, float)

if __name__ == '__main__':
    unittest.main()
```
