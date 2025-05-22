"""
2D Mamba-based Classifier for Multiple Instance Learning.

This implementation uses a stack of Mamba blocks from the 'mamba-ssm' package
to process sequences of instance features.

Reference for Mamba: https://github.com/state-spaces/mamba
Reference for 2DMamba concept: https://github.com/AtlasAnalyticsLab/2DMamba 
(Note: This implementation may simplify or adapt concepts from 2DMamba 
 for direct use in a MIL feature classification context).
"""
import torch
import torch.nn as nn

try:
    from mamba_ssm import Mamba
except ImportError:
    # This is a fallback for environments where mamba_ssm might not be installed.
    # The model will not be usable, but the code can still be imported.
    # A proper installation of mamba_ssm is required to use this model.
    Mamba = None 
    print(
        "Warning: 'mamba_ssm' package not found. Mamba2DClassifier will not be usable. "
        "Please install 'mamba-ssm' (e.g., pip install mamba-ssm causal-conv1d>=1.1.0)."
    )


class Mamba2DClassifier(nn.Module):
    """
    A classifier that uses Mamba blocks to process bags of instance features.
    The "2D" aspect is handled by treating instances as a sequence, which Mamba processes.
    True 2D spatial processing would require more complex patch embedding and scanning patterns.
    """
    def __init__(
        self,
        input_dim: int,
        d_model: int,
        d_state: int = 16,
        d_conv: int = 4,
        expand_factor: int = 2,
        n_layers: int = 4,
        n_classes: int = 2,
        dropout_rate: float = 0.1, # Mamba block itself has a dropout parameter
    ):
        """
        Args:
            input_dim: Dimension of the input instance features.
            d_model: Internal dimension of the Mamba blocks.
            d_state: State dimension for Mamba (SSM N parameter).
            d_conv: Convolution kernel size in Mamba.
            expand_factor: Expansion factor in Mamba's MLP.
            n_layers: Number of Mamba layers to stack.
            n_classes: Number of output classes.
            dropout_rate: Dropout rate for the Mamba blocks' internal dropout.
        """
        super(Mamba2DClassifier, self).__init__()

        if Mamba is None:
            raise ImportError(
                "The 'mamba_ssm' package is required to use Mamba2DClassifier. "
                "Please install it, e.g., 'pip install mamba-ssm causal-conv1d>=1.1.0'."
            )

        self.input_dim = input_dim
        self.d_model = d_model
        self.n_classes = n_classes

        # Project input features to d_model
        self.input_projection = nn.Linear(input_dim, d_model)
        
        # Stack of Mamba blocks
        # Each Mamba block takes (batch_size, seq_len, d_model)
        self.mamba_layers = nn.ModuleList()
        for _ in range(n_layers):
            self.mamba_layers.append(
                Mamba(
                    d_model=d_model,
                    d_state=d_state,
                    d_conv=d_conv,
                    expand=expand_factor, # Corrected parameter name from expand_factor
                    # dropout=dropout_rate, # As of mamba-ssm 1.2.0, dropout is part of MambaMixer
                    # Mamba class itself may not have a direct dropout param.
                    # Dropout is often applied outside or within specific sub-modules of Mamba.
                    # For now, we will rely on dropout in the classification head if needed,
                    # or assume Mamba's internal structure handles regularization.
                    # The Mamba class in mamba_ssm.models.mixer_seq_simple.Mamba
                    # does not seem to take a dropout argument directly in its constructor.
                    # It's often part of a larger configuration or applied separately.
                )
            )

        # Classification head
        # Takes the output of the last Mamba layer (after pooling)
        self.classification_head = nn.Sequential(
            nn.Linear(d_model, d_model // 2), # Intermediate layer
            nn.ReLU(),
            nn.Dropout(dropout_rate if dropout_rate > 0 else 0), # Apply dropout here if desired
            nn.Linear(d_model // 2, n_classes),
        )
        
    def forward(self, H: torch.Tensor) -> torch.Tensor:
        """
        Forward pass for Mamba2DClassifier.

        Args:
            H: Input tensor representing a batch of bags.
               Shape: (batch_size, num_instances, input_dim)
               If a single bag is passed (num_instances, input_dim),
               it should be unsqueezed before calling.
               The `train_model` function typically provides batches.

        Returns:
            logits: Output logits for classification. Shape: (batch_size, n_classes)
        """
        if H.ndim == 2:
            # Assuming a single bag if 2D, needs to be (1, num_instances, input_dim)
            H = H.unsqueeze(0)
        
        batch_size, num_instances, _ = H.shape

        # Project input features to d_model
        # H: (batch_size, num_instances, input_dim) -> (batch_size, num_instances, d_model)
        x = self.input_projection(H)

        # Pass through Mamba layers
        for mamba_layer in self.mamba_layers:
            x = mamba_layer(x) # Mamba block processes (batch, length, dim)

        # Pool instance features to get a single bag representation
        # Mean pooling over the num_instances dimension
        # x: (batch_size, num_instances, d_model) -> (batch_size, d_model)
        bag_representation = torch.mean(x, dim=1)

        # Pass through classification head
        # bag_representation: (batch_size, d_model) -> (batch_size, n_classes)
        logits = self.classification_head(bag_representation)

        return logits

```
