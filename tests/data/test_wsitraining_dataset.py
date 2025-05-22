import unittest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
import pandas as pd
import torch
import numpy as np

# Assuming spinpath is in PYTHONPATH
# from spinpath.data import WSITrainingDataset # Will import this after patching pandas
from spinpath.client.localmodel import ModelConfiguration
# from spinpath.extractors.base import PatchFeatureExtractor # Not strictly needed if extractor methods aren't called

# Dummy PatchFeatureExtractor for testing purposes
class DummyFeatureExtractor:
    def __init__(self, device='cpu', embed_dim=128):
        self.name = "dummy_extractor"
        self.device = torch.device(device)
        self.embed_dim = embed_dim # For testing empty patch handling
        self._model = MagicMock() # Mock internal model
        self._model.num_features = embed_dim # For testing empty patch handling fallback
        self.transform = MagicMock()

class TestWSITrainingDataset(unittest.TestCase):

    def setUp(self):
        # Create a dummy ModelConfiguration
        self.mock_model_config = ModelConfiguration(
            spec_version="1.0",
            model_type="trainable_classifier", # Example
            architecture_name="TestArch",
            patch_size_um=256.0,
            num_classes=2,
            class_names=["class0", "class1"]
        )
        # Create a dummy feature extractor instance
        self.mock_feature_extractor = DummyFeatureExtractor(embed_dim=128)

    @patch('spinpath.data.data.pd.read_csv') # Patch pandas inside spinpath.data.data
    @patch('spinpath.data.data.extract_features_for_slide')
    def test_dataset_initialization_and_len(self, mock_extract_features, mock_read_csv):
        """Test WSITrainingDataset initialization and __len__."""
        dummy_csv_data = "slide_path,label,mask_path\n/path/to/slide1.svs,0,/path/to/mask1.png\n/path/to/slide2.svs,1,\n"
        mock_df = pd.read_csv(mock_open(read_data=dummy_csv_data)()) # Simulate reading the CSV
        mock_read_csv.return_value = mock_df

        from spinpath.data.data import WSITrainingDataset # Import here after patching
        
        dataset = WSITrainingDataset(
            dataset_csv_path=Path("dummy.csv"),
            feature_extractor=self.mock_feature_extractor,
            model_config=self.mock_model_config,
            num_workers_extraction=0,
            quantize_extraction=False
        )
        
        self.assertEqual(len(dataset), 2)
        mock_read_csv.assert_called_once_with(Path("dummy.csv"))

    @patch('spinpath.data.data.pd.read_csv')
    @patch('spinpath.data.data.extract_features_for_slide')
    def test_getitem_successful_extraction(self, mock_extract_features, mock_read_csv):
        """Test __getitem__ with successful feature extraction."""
        dummy_csv_data = "slide_path,label\n/path/to/slide1.svs,0\n"
        mock_df = pd.read_csv(mock_open(read_data=dummy_csv_data)())
        mock_read_csv.return_value = mock_df

        # Mock return value for extract_features_for_slide
        dummy_embeddings = np.random.rand(10, 128).astype(np.float32) # 10 patches, 128 dim
        dummy_coords = np.random.randint(0, 1000, size=(10, 2)).astype(np.int_)
        mock_extract_features.return_value = (dummy_embeddings, dummy_coords)

        from spinpath.data.data import WSITrainingDataset
        dataset = WSITrainingDataset(
            dataset_csv_path=Path("dummy.csv"),
            feature_extractor=self.mock_feature_extractor,
            model_config=self.mock_model_config,
            num_workers_extraction=0,
            quantize_extraction=False,
            label_transform=lambda x: int(x) # Example transform
        )
        
        embeddings_tensor, label_tensor, coords_tensor = dataset[0]
        
        mock_extract_features.assert_called_once_with(
            slide_path=Path("/path/to/slide1.svs"),
            extractor=self.mock_feature_extractor,
            model_config=self.mock_model_config,
            tissue_mask_path=None, # Since mask_path is not in CSV
            num_workers_extraction=0,
            quantize=False
        )
        
        self.assertIsInstance(embeddings_tensor, torch.Tensor)
        self.assertTrue(torch.equal(embeddings_tensor, torch.from_numpy(dummy_embeddings).float()))
        self.assertEqual(embeddings_tensor.shape, (10, 128))
        
        self.assertIsInstance(label_tensor, torch.Tensor)
        self.assertEqual(label_tensor.item(), 0)
        self.assertEqual(label_tensor.dtype, torch.long)
        
        self.assertIsInstance(coords_tensor, torch.Tensor)
        self.assertTrue(torch.equal(coords_tensor, torch.from_numpy(dummy_coords).int()))
        self.assertEqual(coords_tensor.shape, (10, 2))

    @patch('spinpath.data.data.pd.read_csv')
    @patch('spinpath.data.data.extract_features_for_slide')
    def test_getitem_no_patches(self, mock_extract_features, mock_read_csv):
        """Test __getitem__ when extract_features_for_slide returns no patches."""
        dummy_csv_data = "slide_path,label\n/path/to/slide_empty.svs,1\n"
        mock_df = pd.read_csv(mock_open(read_data=dummy_csv_data)())
        mock_read_csv.return_value = mock_df

        # Mock extract_features_for_slide to return empty arrays
        empty_embeddings = np.array([], dtype=np.float32).reshape(0, self.mock_feature_extractor.embed_dim)
        empty_coords = np.array([], dtype=np.int_).reshape(0, 2)
        mock_extract_features.return_value = (empty_embeddings, empty_coords)
        
        from spinpath.data.data import WSITrainingDataset
        dataset = WSITrainingDataset(
            dataset_csv_path=Path("dummy_empty.csv"),
            feature_extractor=self.mock_feature_extractor,
            model_config=self.mock_model_config,
            num_workers_extraction=0,
            quantize_extraction=False
        )
        
        embeddings_tensor, label_tensor, coords_tensor = dataset[0]
        
        self.assertIsInstance(embeddings_tensor, torch.Tensor)
        self.assertEqual(embeddings_tensor.shape, (0, self.mock_feature_extractor.embed_dim))
        
        self.assertIsInstance(label_tensor, torch.Tensor)
        self.assertEqual(label_tensor.item(), 1)
        
        self.assertIsInstance(coords_tensor, torch.Tensor)
        self.assertEqual(coords_tensor.shape, (0, 2))

    @patch('spinpath.data.data.pd.read_csv')
    @patch('spinpath.data.data.extract_features_for_slide')
    def test_getitem_with_mask_path(self, mock_extract_features, mock_read_csv):
        """Test __getitem__ when mask_path is provided and exists."""
        # Must patch Path.exists for the mask_path check
        with patch('spinpath.data.data.Path.exists') as mock_path_exists:
            mock_path_exists.return_value = True # Simulate mask file existing

            dummy_csv_data = "slide_path,label,mask_path\n/path/to/slide_masked.svs,0,/path/to/mask.png\n"
            mock_df = pd.read_csv(mock_open(read_data=dummy_csv_data)())
            mock_read_csv.return_value = mock_df

            dummy_embeddings = np.random.rand(5, 128).astype(np.float32)
            dummy_coords = np.random.randint(0, 500, size=(5, 2)).astype(np.int_)
            mock_extract_features.return_value = (dummy_embeddings, dummy_coords)

            from spinpath.data.data import WSITrainingDataset
            dataset = WSITrainingDataset(
                dataset_csv_path=Path("dummy_masked.csv"),
                feature_extractor=self.mock_feature_extractor,
                model_config=self.mock_model_config,
                num_workers_extraction=0,
                quantize_extraction=False
            )
            
            dataset[0] # Trigger __getitem__
            
            mock_extract_features.assert_called_once_with(
                slide_path=Path("/path/to/slide_masked.svs"),
                extractor=self.mock_feature_extractor,
                model_config=self.mock_model_config,
                tissue_mask_path=Path("/path/to/mask.png"), # Check if mask_path is passed
                num_workers_extraction=0,
                quantize=False
            )
            mock_path_exists.assert_any_call() # Check Path.exists was called for the mask

if __name__ == '__main__':
    unittest.main()
```
