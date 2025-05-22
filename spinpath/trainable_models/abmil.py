"""
Attention-based Multiple Instance Learning (ABMIL) model.

Reference: Ilse, M., Tomczak, J. M., & Welling, M. (2018, July). 
Attention-based deep multiple instance learning. 
In International conference on machine learning (pp. 2127-2136). PMLR.
GitHub Reference: https://github.com/AMLab-Amsterdam/AttentionDeepMIL
"""
import torch
import torch.nn as nn
import torch.nn.functional as F

class ABMIL(nn.Module):
    """
    Attention-based Multiple Instance Learning (ABMIL) model.
    """
    def __init__(self, input_dim: int, hidden_dim: int = 128, n_classes: int = 2, dropout_rate: float = 0.0):
        """
        Args:
            input_dim: Dimension of the input instance features.
            hidden_dim: Dimension for the attention mechanism's hidden layer (L_dim).
            n_classes: Number of output classes.
            dropout_rate: Dropout rate to apply after concatenating attention-weighted features.
                          Default is 0.0 (no dropout).
        """
        super(ABMIL, self).__init__()
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.n_classes = n_classes
        self.dropout_rate = dropout_rate

        # Attention mechanism layers
        # Paper uses Gated Attention:
        # A_V = tanh(H @ W_v)
        # A_U = sigmoid(H @ W_u)
        # A = softmax(W @ (A_V * A_U))
        # H is (N_instances, input_dim)
        # W_v, W_u are (input_dim, hidden_dim)
        # W is (hidden_dim, 1)

        self.attention_V = nn.Linear(self.input_dim, self.hidden_dim)
        self.attention_U = nn.Linear(self.input_dim, self.hidden_dim)
        self.attention_weights = nn.Linear(self.hidden_dim, 1)

        # Classifier
        # The paper's implementation uses a single linear layer for classification.
        # Output should be raw logits for compatibility with nn.CrossEntropyLoss or nn.BCEWithLogitsLoss.
        self.classifier = nn.Linear(self.input_dim, self.n_classes)
        
        if self.dropout_rate > 0:
            self.dropout = nn.Dropout(self.dropout_rate)
        else:
            self.dropout = nn.Identity() # No-op if dropout_rate is 0

    def forward(self, H: torch.Tensor):
        """
        Forward pass for ABMIL.

        Args:
            H: Input tensor representing a batch of bags.
               Shape: (batch_size, num_instances, input_dim)
               If a single bag is passed with shape (num_instances, input_dim),
               it will be unsqueezed to (1, num_instances, input_dim).

        Returns:
            logits: Output logits for classification. Shape: (batch_size, n_classes)
            # A: Attention weights (optional, can be returned for interpretability).
            #    Shape: (batch_size, num_instances, 1)
        """
        # Ensure H is 3D: (batch_size, num_instances, input_dim)
        if H.ndim == 2:
            H = H.unsqueeze(0)  # Convert (num_instances, input_dim) to (1, num_instances, input_dim)
        
        # Gated attention mechanism
        A_V = torch.tanh(self.attention_V(H))  # (batch_size, num_instances, hidden_dim)
        A_U = torch.sigmoid(self.attention_U(H))  # (batch_size, num_instances, hidden_dim)
        
        # Element-wise multiplication
        att_intermediate = A_V * A_U  # (batch_size, num_instances, hidden_dim)
        
        # Get attention scores (unnormalized)
        A_unnormalized = self.attention_weights(att_intermediate)  # (batch_size, num_instances, 1)
        
        # Apply softmax to get normalized attention weights
        # These weights indicate the importance of each instance in a bag.
        A = F.softmax(A_unnormalized, dim=1)  # Softmax over num_instances dimension

        # Compute the bag representation (M) by weighted sum of instance features
        # M = sum_{k=1}^{K} (A_k * H_k)
        # H is (batch_size, num_instances, input_dim)
        # A is (batch_size, num_instances, 1)
        # M should be (batch_size, input_dim)
        M = torch.sum(A * H, dim=1)  # (batch_size, input_dim)

        # Apply dropout if specified
        M = self.dropout(M)

        # Pass the bag representation through the classifier
        logits = self.classifier(M)  # (batch_size, n_classes)

        # To align with train_model, only return logits.
        # If attention weights are needed for other purposes (e.g., visualization),
        # the model or training loop might need adjustment.
        return logits
        # return logits, A # Uncomment if attention weights are needed as an output

```
