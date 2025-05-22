import unittest
from unittest.mock import patch, MagicMock

import torch
from torchvision.transforms import Compose

# Make sure spinpath is in PYTHONPATH or adjust path accordingly
# from spinpath.extractors.uni2 import UNI2 # This would be the direct import
# For testing, it's often better to patch the dependencies of the module under test.

class TestUNI2Extractor(unittest.TestCase):

    @patch('spinpath.extractors.uni2.timm')
    def test_uni2_name_and_initialization(self, mock_timm):
        """Test UNI2 extractor name and basic initialization (mocking timm)."""
        # Mock timm.create_model to avoid actual model loading
        mock_model_instance = MagicMock(spec=torch.nn.Module)
        mock_model_instance.eval.return_value = mock_model_instance
        mock_model_instance.to.return_value = mock_model_instance
        mock_model_instance.pretrained_cfg = {'mean': (0.5, 0.5, 0.5), 'std': (0.5, 0.5, 0.5), 'input_size': (3, 224, 224)} # Example
        
        mock_timm.create_model.return_value = mock_model_instance
        
        # Mock timm.data.resolve_data_config and timm.data.create_transform
        # as they are called during PatchFeatureExtractor initialization via self.transform
        mock_timm.data.resolve_data_config.return_value = {'input_size': (3, 224, 224), 'interpolation': 'bilinear', 'mean': (0.5,0.5,0.5), 'std': (0.5,0.5,0.5)}
        mock_timm.data.create_transform.return_value = MagicMock(spec=Compose)

        # Dynamically import UNI2 here to ensure patches are active
        from spinpath.extractors.uni2 import UNI2
        extractor = UNI2(device='cpu')
        
        self.assertEqual(extractor.name, "UNI2")
        self.assertIsNotNone(extractor)
        self.assertTrue(mock_timm.create_model.called) # From load_model
        self.assertTrue(mock_timm.data.resolve_data_config.called) # From PatchFeatureExtractor init
        self.assertTrue(mock_timm.data.create_transform.called) # From PatchFeatureExtractor init


    @patch('spinpath.extractors.uni2.timm')
    def test_uni2_load_model(self, mock_timm):
        """Test UNI2.load_model() behavior."""
        mock_model_instance = MagicMock(spec=torch.nn.Module)
        mock_model_instance.eval.return_value = mock_model_instance
        mock_model_instance.to.return_value = mock_model_instance
        
        mock_timm.create_model.return_value = mock_model_instance

        # To test load_model, we need UNI2 class, but avoid PatchFeatureExtractor's __init__ transform call
        from spinpath.extractors.uni2 import UNI2
        
        # Temporarily disable transform creation for this specific test if it interferes
        with patch.object(UNI2, 'transform', new_callable=MagicMock) as mock_transform_prop:
            extractor = UNI2(device='cpu') # PatchFeatureExtractor.__init__ calls load_model

        mock_timm.create_model.assert_called_once_with(
            "hf-hub:MahmoodLab/UNI2-h",
            pretrained=True,
            num_classes=0
        )
        mock_model_instance.eval.assert_called_once()
        mock_model_instance.to.assert_called_once_with(torch.device('cpu'))
        self.assertIs(extractor._model, mock_model_instance)


    @patch('spinpath.extractors.uni2.timm')
    def test_uni2_transform_property(self, mock_timm):
        """Test UNI2.transform property logic."""
        mock_model_instance = MagicMock(spec=torch.nn.Module)
        mock_model_instance.eval.return_value = mock_model_instance
        mock_model_instance.to.return_value = mock_model_instance
        # Provide a dummy pretrained_cfg for resolve_data_config
        mock_model_instance.pretrained_cfg = {'mean': (0.5, 0.5, 0.5), 'std': (0.5, 0.5, 0.5), 'input_size': (3, 224, 224)}
        mock_timm.create_model.return_value = mock_model_instance

        mock_data_config = {'input_size': (3, 224, 224), 'interpolation': 'bilinear', 'mean': (0.5,0.5,0.5), 'std': (0.5,0.5,0.5)}
        mock_timm.data.resolve_data_config.return_value = mock_data_config
        
        mock_transform_instance = MagicMock(spec=Compose)
        mock_timm.data.create_transform.return_value = mock_transform_instance

        from spinpath.extractors.uni2 import UNI2
        extractor = UNI2(device='cpu') # This will call load_model and set up _model

        # Access the transform property
        transform = extractor.transform
        
        mock_timm.data.resolve_data_config.assert_called_with(model=mock_model_instance)
        mock_timm.data.create_transform.assert_called_with(**mock_data_config)
        self.assertIs(transform, mock_transform_instance)

    @patch('spinpath.extractors.uni2.timm') # Patch timm for UNI2 instantiation
    def test_uni2_get_batch_embeddings(self, mock_timm_init):
        """Test get_batch_embeddings with a dummy input tensor."""
        # Mock for UNI2 instantiation
        mock_model_instance_init = MagicMock(spec=torch.nn.Module)
        mock_model_instance_init.eval.return_value = mock_model_instance_init
        mock_model_instance_init.to.return_value = mock_model_instance_init
        mock_model_instance_init.pretrained_cfg = {'mean': (0.5,0.5,0.5), 'std': (0.5,0.5,0.5), 'input_size': (3,224,224)}
        mock_timm_init.create_model.return_value = mock_model_instance_init
        mock_timm_init.data.resolve_data_config.return_value = {}
        mock_timm_init.data.create_transform.return_value = MagicMock(spec=Compose)

        from spinpath.extractors.uni2 import UNI2
        extractor = UNI2(device='cpu')

        # Mock the actual model's forward pass for get_batch_embeddings
        mock_forward_output = torch.randn(2, 1024) # Batch of 2, embedding dim 1024
        extractor._model.forward = MagicMock(return_value=mock_forward_output)
        # If UNI2 overrides forward or uses forward_features, mock that instead:
        # extractor._model.forward_features = MagicMock(return_value=mock_forward_output)

        dummy_input = torch.randn(2, 3, 224, 224)  # Batch of 2 images
        
        with torch.no_grad(): # get_batch_embeddings uses torch.no_grad()
            embeddings = extractor.get_batch_embeddings(dummy_input)

        extractor._model.forward.assert_called_once_with(dummy_input.to(torch.device('cpu')))
        self.assertTrue(torch.equal(embeddings, mock_forward_output.cpu()))
        self.assertEqual(embeddings.shape, (2, 1024))

if __name__ == '__main__':
    unittest.main()
```
