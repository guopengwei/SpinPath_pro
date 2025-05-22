# SpinPath

[![Continuous Integration](https://github.com/SBU-BMI/spinpath/actions/workflows/cli-test.yml/badge.svg)](https://github.com/SBU-BMI/spinpath/actions/workflows/cli-test.yml)
[![Version on PyPI](https://img.shields.io/pypi/v/spinpath.svg)](https://pypi.org/project/spinpath/)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/spinpath)](https://pypi.org/project/spinpath/)

SpinPath is a command line tool to run pre-trained MIL models on whole slide images, and also supports training custom MIL models. It is the slide-level companion to [WSInfer](https://wsinfer.readthedocs.io/en/latest/), which provides patch-level classification.

> [!CAUTION]
> SpinPath is intended _only_ for research purposes.

# Install

SpinPath can be installed using `pip`. SpinPath will install PyTorch automatically
if it is not installed, but this may not install GPU-enabled PyTorch even if a GPU is available.
For this reason, _install PyTorch before installing SpinPath_.

## Install PyTorch first

Please see [PyTorch's installation instructions](https://pytorch.org/get-started/locally/)
for help installing PyTorch. The installation instructions differ based on your operating system
and choice of `pip` or `conda`. Thankfully, the instructions provided
by PyTorch also install the appropriate version of CUDA. We refrain from including code
examples of installation commands because these commands can change over time. Please
refer to [PyTorch's installation instructions](https://pytorch.org/get-started/locally/)
for the most up-to-date instructions.

You will need a new-enough driver for your NVIDIA GPU. Please see
[this version compatibility table](https://docs.nvidia.com/deploy/cuda-compatibility/#minor-version-compatibility)
for the minimum versions required for different CUDA versions.

To test whether PyTorch can detect your GPU, check that this code snippet prints `True`.

```
python -c 'import torch; print(torch.cuda.is_available())'
```

## Install SpinPath with pip

```
pip install spinpath
```
For training models like `Mamba2DClassifier`, you might need additional dependencies:
```bash
pip install mamba-ssm causal-conv1d>=1.1.0
```

# Examples

> [!CAUTION]
> These models are intended _only_ for research purposes.

## Running Inference with a Pre-trained Model Online

Jakub Kaczmarzyk has uploaded several pre-trained MIL models to HuggingFace for the community to explore. Over time, I (Jakub) hope that others may contribute MIL models too. If you are interested in this, please feel free to email me at jakub.kaczmarzyk at stonybrookmedicine dot edu.

The models are available at https://huggingface.co/kaczmarj

### TP53 mutation prediction

```
spinpath run -m kaczmarj/pancancer-tp53-mut.tcga -i slide.svs
```

### Cancer tissue classification

```
spinpath run -m kaczmarj/pancancer-tissue-classifier.tcga -i slide.svs
```

### Metastasis prediction in axillary lymph nodes

```
spinpath run -m kaczmarj/breast-lymph-nodes-metastasis.camelyon16 -i slide.svs
```

### Survival prediction in GBM-LGG

```
spinpath run -m kaczmarj/gbmlgg-survival-porpoise.tcga -i slide.svs
```

### Survival prediction in kidney renal papillary cell carcinoma

```
spinpath run -m kaczmarj/kirp-survival-porpoise.tcga -i slide.svs
```


## Running Inference with a Local (potentially private) Model

You can use SpinPath with a local MIL model. The model must be saved to TorchScript format, and a model configuration file must also be written.

Here is an example of a configuration JSON file for a pre-trained TorchScript model:

```json
{
    "spec_version": "1.0",
    "type": "abmil",
    "patch_size_um": 128,
    "feature_extractor": "ctranspath",
    "num_classes": 2,
    "class_names": [
        "wildtype",
        "mutant"
    ]
}
```

There is a JSON schema in `spinpath/schemas/model-config.schema.json` for reference. This schema has been updated to support configurations for both inference and training.

Once you have the model in TorchScript format and the configuration JSON file, you can run the model on slides. For example:

```
spinpath runlocal -m model.pt -c model.config.json \
    -i slides/TCGA-3L-AA1B-01Z-00-DX1.8923A151-A690-40B7-9E5A-FCBEDFC2394F.svs
```

# Training Models with SpinPath

SpinPath now supports training custom Multiple Instance Learning (MIL) models using your own datasets. This allows you to leverage the feature extraction capabilities of SpinPath and train models like ABMIL or Mamba-based classifiers on these features.

## Supported Components for Training

When training models, you'll be working with two main components:

*   **Trainable Models:** These are the MIL architectures that learn to classify whole slide images based on extracted features. Currently supported trainable models include:
    *   `ABMIL`: Attention-based Multiple Instance Learning model.
    *   `Mamba2DClassifier`: A Mamba-based model adapted for MIL tasks. (Requires `mamba-ssm` package).
*   **Feature Extractors:** These models are used to generate feature vectors (embeddings) from image patches. These features then become the input to the trainable models. Supported extractors for training include:
    *   `UNI2`: A powerful vision foundation model.
    *   Other extractors available in SpinPath (e.g., `CTransPath`, `Virchow`, `Phikon`, etc.) can also be used. Ensure the chosen extractor's output dimension matches the `input_dim` expected by your trainable model.

## The `spinpath train` Command

The primary interface for training is the `spinpath train` command.

**Basic Syntax:**

```bash
spinpath train --dataset-csv path/to/your_dataset.csv \
               --model-name ABMIL \
               --feature-extractor-name UNI2 \
               --model-config-path path/to/your_model_config.json \
               --output-dir path/to/save_outputs \
               [OTHER_OPTIONS]
```

**Key Options:**

*   `--dataset-csv PATH`: **Required.** Path to your dataset's CSV file. This file tells SpinPath where your slides are and what their labels are.
    *   **Format:** The CSV must contain at least `slide_path` and `label` columns.
    *   An optional `mask_path` column can be included to specify pre-computed tissue masks for each slide. If not provided, SpinPath will segment tissue automatically.
    *   **Example `dataset.csv`:**
        ```csv
        slide_path,label,mask_path
        /data/slides/slide001.svs,Tumor,/data/masks/slide001_mask.png
        /data/slides/slide002.svs,Normal,
        /data/slides/slide003.svs,Tumor,
        ```
        Labels can be strings or integers. If strings, ensure your `model-config.json`'s `class_names` and `num_classes` match. SpinPath will attempt a basic conversion to integer labels based on the order in `class_names` (e.g., if `class_names: ["Normal", "Tumor"]`, then "Normal" becomes 0, "Tumor" becomes 1).

*   `--model-name {ABMIL|Mamba2DClassifier|...}`: **Required.** Specifies the trainable MIL model architecture to use. Use `spinpath train --help` to see a list of all available models.

*   `--feature-extractor-name {UNI2|CTransPath|...}`: **Required.** Specifies the feature extractor to use for generating patch embeddings. Use `spinpath train --help` to see a list of all available extractors.

*   `--model-config-path PATH`: **Required.** Path to a JSON configuration file for your training run. This file defines how the trainable model is constructed and what feature extractor to use.
    *   **Role:** It links the feature extractor, its patch settings, and the trainable model's architecture and output classes.
    *   **Example `model-config.json` for training:**
        ```json
        {
          "spec_version": "1.0",
          "model_type": "trainable_classifier",
          "architecture_name": "ABMIL",
          "architecture_params": {
            "hidden_dim": 256,
            "dropout_rate": 0.25
          },
          "feature_extractor": "UNI2",
          "patch_size_um": [256, 256],
          "class_names": ["Normal", "Tumor"],
          "num_classes": 2
        }
        ```
        *   `model_type`: Should be `"trainable_classifier"` for training.
        *   `architecture_name`: Matches the `--model-name` (e.g., "ABMIL").
        *   `architecture_params`: Parameters passed to the trainable model's constructor (e.g., `hidden_dim` for ABMIL, or `d_model`, `n_layers` for Mamba2DClassifier).
        *   `feature_extractor`: Name of the feature extractor. This should align with the features you intend to use.
        *   `patch_size_um`: Defines the size of patches to extract, in micrometers (can be a single number for square patches or `[width, height]`).
        *   `class_names`, `num_classes`: Define the output classes for your classifier. `num_classes` should match the output dimension of your trainable model and the length of `class_names`.

*   `--output-dir PATH`: **Required.** Directory where training outputs (model checkpoints like `[model-name]_final.pth`, logs, and the final `model_config.json`) will be saved.

*   **Hyperparameters:**
    *   `--num-epochs INT`: Number of training epochs (default: 10).
    *   `--learning-rate FLOAT`: Initial learning rate (default: 0.0001).
    *   `--batch-size INT`: Number of bags (slides) per training iteration (default: 1, common for MIL).
    *   Other options for optimizer, loss function, LR scheduler, etc., are available. Use `spinpath train --help` for details.

## Example Training Workflow

1.  **Prepare your dataset CSV:** Create a `dataset.csv` file as described above, listing paths to your slide images and their corresponding labels.
2.  **Prepare your `model-config.json`:** Define your model architecture, feature extractor, and output classes as in the example above.
3.  **Run Training:**
    ```bash
    spinpath train \
        --dataset-csv ./my_dataset.csv \
        --model-name ABMIL \
        --feature-extractor-name UNI2 \
        --model-config-path ./my_abmil_config.json \
        --output-dir ./training_output_abmil \
        --num-epochs 20 \
        --learning-rate 0.0005 \
        --device cuda
    ```
    This command will:
    *   Read `my_dataset.csv`.
    *   For each slide, extract features using the `UNI2` extractor with patch settings from `my_abmil_config.json`. These features are cached locally.
    *   Train an `ABMIL` model (with `hidden_dim: 256`, `dropout_rate: 0.25` as per the example config) on these features.
    *   Save the trained model (`ABMIL_final.pth`) and the used configuration to `./training_output_abmil/`.

## Dependencies for Training

*   If using `Mamba2DClassifier`, you need to install `mamba-ssm` and its dependency `causal-conv1d`. This can be done via pip:
    ```bash
    pip install mamba-ssm causal-conv1d>=1.1.0
    ```
    This may involve C++/CUDA compilation steps. Other models do not require extra dependencies beyond the standard SpinPath installation.

## Preprocessing and Feature Consistency

SpinPath uses the same underlying feature extraction pipeline (`spinpath.feature_pipeline.extract_features_for_slide`) for both training (via `WSITrainingDataset`) and inference. This ensures that the features your model is trained on are generated in the same way as they will be during inference. (Note: Full CLI support for inference with newly trained non-TorchScript models is planned for future updates).

# How it works from 30,000 feet

The pipeline for attention-based MIL methods is rather standardized. Here are the steps that SpinPath takes. In the future, we would like to incorporate inference using graph-based methods, so this workflow will likely have to be modified.

1. Segment the tissue in the image.
2. Create patches of the tissue regions.
3. Run a feature extractor on these patches.
4. Run the pre-trained model on the extracted features.
5. Save the results of the extracted features.

SpinPath caches steps 1, 2, and 3, as those can be reused among MIL models. Step 3 (feature extraction) is often the bottleneck of the workflow, and reusing extracted features can reduce runtime considerably.

# Developers

Clone and install `spinpath`:

Clone the repository and make a virtual environment for it. Then install the dependencies, with `dev` extras.

```
pip install -e .[dev]
```

Configure `pre-commit` to run the formatter before commits happen.

```
pre-commit install
```
