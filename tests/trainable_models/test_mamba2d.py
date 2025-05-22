import unittest
from unittest.mock import patch, MagicMock
import torch

# Import Mamba2DClassifier from your project
# from spinpath.trainable_models.mamba2d import Mamba2DClassifier

# Define a mock Mamba class that can be used by the Mamba2DClassifier
class MockMamba(torch.nn.Module):
    def __init__(self, d_model, d_state, d_conv, expand):
        super().__init__()
        self.d_model = d_model
        # Store args to allow verification if needed
        self.d_state_arg = d_state
        self.d_conv_arg = d_conv
        self.expand_arg = expand
        # A simple linear layer to simulate some transformation and ensure parameters exist
        self.dummy_layer = torch.nn.Linear(d_model, d_model) 

    def forward(self, x):
        # Just return the input or a slightly modified version
        return self.dummy_layer(x)

class TestMamba2DClassifier(unittest.TestCase):

    @patch('spinpath.trainable_models.mamba2d.Mamba', new=MockMamba)
    def test_mamba2d_instantiation(self):
        """Test Mamba2DClassifier instantiation with mocked Mamba."""
        from spinpath.trainable_models.mamba2d import Mamba2DClassifier # Import after patching

        input_dim = 256
        d_model = 128
        n_layers = 2
        n_classes = 3
        
        model = Mamba2DClassifier(
            input_dim=input_dim,
            d_model=d_model,
            d_state=16,
            d_conv=4,
            expand_factor=2,
            n_layers=n_layers,
            n_classes=n_classes,
            dropout_rate=0.1
        )
        
        self.assertIsInstance(model, Mamba2DClassifier)
        self.assertEqual(model.input_dim, input_dim)
        self.assertEqual(model.d_model, d_model)
        self.assertEqual(model.n_classes, n_classes)
        self.assertIsInstance(model.input_projection, torch.nn.Linear)
        self.assertEqual(len(model.mamba_layers), n_layers)
        for layer in model.mamba_layers:
            self.assertIsInstance(layer, MockMamba) # Check if our mock was used
            self.assertEqual(layer.d_model, d_model) # Check if d_model was passed correctly
        self.assertIsInstance(model.classification_head, torch.nn.Sequential)

    @patch('spinpath.trainable_models.mamba2d.Mamba', new=MockMamba)
    def test_mamba2d_forward_pass_single_bag(self):
        """Test Mamba2DClassifier forward pass with a single bag."""
        from spinpath.trainable_models.mamba2d import Mamba2DClassifier

        input_dim = 256
        d_model = 128
        n_classes = 2
        num_instances = 20
        
        model = Mamba2DClassifier(
            input_dim=input_dim,
            d_model=d_model,
            n_layers=1,
            n_classes=n_classes
        )
        model.eval() # Set to eval mode

        # Single bag: (num_instances, input_dim)
        dummy_input = torch.randn(num_instances, input_dim)
        
        with torch.no_grad():
            logits = model(dummy_input)
        
        self.assertIsInstance(logits, torch.Tensor)
        # Output shape should be (1, n_classes) due to unsqueezing
        self.assertEqual(logits.shape, (1, n_classes))

    @patch('spinpath.trainable_models.mamba2d.Mamba', new=MockMamba)
    def test_mamba2d_forward_pass_batch_of_bags(self):
        """Test Mamba2DClassifier forward pass with a batch of bags."""
        from spinpath.trainable_models.mamba2d import Mamba2DClassifier

        input_dim = 256
        d_model = 128
        n_classes = 3
        batch_size = 4
        num_instances = 10
        
        model = Mamba2DClassifier(
            input_dim=input_dim,
            d_model=d_model,
            n_layers=2,
            n_classes=n_classes,
            dropout_rate=0.0 # No dropout in classification head for this test
        )
        model.eval()

        # Batch of bags: (batch_size, num_instances, input_dim)
        dummy_input = torch.randn(batch_size, num_instances, input_dim)
        
        with torch.no_grad():
            logits = model(dummy_input)
            
        self.assertIsInstance(logits, torch.Tensor)
        self.assertEqual(logits.shape, (batch_size, n_classes))

    @patch('spinpath.trainable_models.mamba2d.Mamba', new=None) # Simulate mamba_ssm not being installed
    def test_mamba2d_import_error_if_mamba_not_installed(self):
        """Test that Mamba2DClassifier raises ImportError if mamba_ssm.Mamba is None."""
        # This requires re-importing or reloading the module where Mamba2DClassifier is defined.
        # Python's import system caches modules, so we need to handle this carefully.
        # One way is to unload and reload the module.
        import sys
        if 'spinpath.trainable_models.mamba2d' in sys.modules:
            del sys.modules['spinpath.trainable_models.mamba2d']
        
        with self.assertRaisesRegex(ImportError, "The 'mamba_ssm' package is required"):
            from spinpath.trainable_models.mamba2d import Mamba2DClassifier
            # Attempt to instantiate if the import itself doesn't raise it (depends on module structure)
            # model = Mamba2DClassifier(input_dim=10, d_model=10)


if __name__ == '__main__':
    unittest.main()
```
