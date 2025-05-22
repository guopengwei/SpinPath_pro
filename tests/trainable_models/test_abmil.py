import unittest
import torch
from spinpath.trainable_models.abmil import ABMIL

class TestABMIL(unittest.TestCase):

    def test_abmil_instantiation(self):
        """Test ABMIL model instantiation."""
        model = ABMIL(input_dim=128, hidden_dim=64, n_classes=2, dropout_rate=0.1)
        self.assertIsInstance(model, ABMIL)
        self.assertEqual(model.input_dim, 128)
        self.assertEqual(model.hidden_dim, 64)
        self.assertEqual(model.n_classes, 2)
        self.assertEqual(model.dropout_rate, 0.1)
        self.assertIsNotNone(model.attention_V)
        self.assertIsNotNone(model.attention_U)
        self.assertIsNotNone(model.attention_weights)
        self.assertIsNotNone(model.classifier)
        self.assertIsNotNone(model.dropout)

    def test_abmil_forward_pass_single_bag(self):
        """Test ABMIL forward pass with a single bag."""
        input_dim = 128
        n_classes = 3
        num_instances = 10

        model = ABMIL(input_dim=input_dim, hidden_dim=64, n_classes=n_classes, dropout_rate=0.0)
        model.eval() # Set to eval mode to disable dropout for consistent output shape

        # Single bag: (num_instances, input_dim)
        dummy_input = torch.randn(num_instances, input_dim)
        
        with torch.no_grad():
            logits = model(dummy_input)

        self.assertIsInstance(logits, torch.Tensor)
        # Output shape should be (1, n_classes) because a single bag is unsqueezed to batch_size=1
        self.assertEqual(logits.shape, (1, n_classes))

    def test_abmil_forward_pass_batch_of_bags(self):
        """Test ABMIL forward pass with a batch of bags."""
        input_dim = 128
        n_classes = 2
        batch_size = 4
        num_instances = 15 # Can vary per bag if using custom collate, but fixed for this test

        model = ABMIL(input_dim=input_dim, hidden_dim=64, n_classes=n_classes, dropout_rate=0.25)
        model.eval()

        # Batch of bags: (batch_size, num_instances, input_dim)
        dummy_input = torch.randn(batch_size, num_instances, input_dim)

        with torch.no_grad():
            logits = model(dummy_input)
        
        self.assertIsInstance(logits, torch.Tensor)
        self.assertEqual(logits.shape, (batch_size, n_classes))

    def test_abmil_forward_pass_with_dropout(self):
        """Test ABMIL forward pass with dropout enabled."""
        input_dim = 128
        n_classes = 2
        batch_size = 2
        num_instances = 5

        model = ABMIL(input_dim=input_dim, hidden_dim=64, n_classes=n_classes, dropout_rate=0.5)
        # Keep model in training mode to ensure dropout is active
        model.train() 

        dummy_input = torch.randn(batch_size, num_instances, input_dim)
        
        # Running forward twice with dropout should ideally give different results,
        # but it's hard to assert reliably. The main thing is that it runs.
        # We can check if dropout layer is not nn.Identity
        self.assertNotIsInstance(model.dropout, torch.nn.Identity)

        logits = model(dummy_input) # No torch.no_grad() here
        
        self.assertIsInstance(logits, torch.Tensor)
        self.assertEqual(logits.shape, (batch_size, n_classes))

if __name__ == '__main__':
    unittest.main()
```
