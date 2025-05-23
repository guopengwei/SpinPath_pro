#!/usr/bin/env python3
"""
Create a test image for the SpinPath Image Viewer

This creates a multi-level TIFF image that can be used to test the tile server
and image viewer functionality.
"""

import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import tifffile as tiff

def create_test_slide(width=4096, height=4096, levels=4):
    """Create a multi-level test slide image"""
    
    print(f"Creating test slide {width}x{height} with {levels} levels...")
    
    # Create base image
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Draw a grid pattern
    grid_size = 256
    colors = ['red', 'green', 'blue', 'yellow', 'cyan', 'magenta']
    
    for x in range(0, width, grid_size):
        for y in range(0, height, grid_size):
            color_idx = ((x // grid_size) + (y // grid_size)) % len(colors)
            color = colors[color_idx]
            
            # Draw rectangle
            draw.rectangle([x, y, x + grid_size - 10, y + grid_size - 10], 
                         fill=color, outline='black', width=2)
            
            # Add text
            try:
                draw.text((x + 10, y + 10), f"{x//grid_size},{y//grid_size}", 
                         fill='black')
            except:
                pass  # Font might not be available
    
    # Add some circles and shapes for visual interest
    for i in range(20):
        x = np.random.randint(0, width - 100)
        y = np.random.randint(0, height - 100)
        r = np.random.randint(20, 50)
        color = colors[i % len(colors)]
        draw.ellipse([x, y, x + r, y + r], fill=color, outline='black')
    
    return img

def save_as_pyramidal_tiff(image, filename):
    """Save image as a pyramidal TIFF"""
    
    print(f"Saving pyramidal TIFF: {filename}")
    
    # Convert PIL image to numpy array
    img_array = np.array(image)
    
    # Create pyramid levels
    levels = []
    current = img_array
    
    # Add original resolution
    levels.append(current)
    
    # Create downsampled levels
    for i in range(3):  # 3 additional levels
        # Downsample by factor of 2
        h, w = current.shape[:2]
        new_h, new_w = h // 2, w // 2
        
        if new_h < 256 or new_w < 256:
            break
            
        # Simple downsampling
        downsampled = current[::2, ::2]
        levels.append(downsampled)
        current = downsampled
    
    # Save as pyramidal TIFF
    with tiff.TiffWriter(filename) as tif:
        for i, level in enumerate(levels):
            tif.write(level, 
                     subfiletype=1 if i > 0 else 0,  # Mark as reduced resolution
                     tile=(256, 256))  # Use 256x256 tiles
    
    print(f"Created {len(levels)} pyramid levels")
    return len(levels)

def main():
    """Create test images"""
    
    os.makedirs("test_data", exist_ok=True)
    
    # Create a medium-sized test image
    print("Creating medium test slide...")
    img_medium = create_test_slide(2048, 2048, 3)
    save_as_pyramidal_tiff(img_medium, "test_data/test_slide_medium.tiff")
    
    # Create a small test image
    print("\nCreating small test slide...")
    img_small = create_test_slide(1024, 1024, 2)
    save_as_pyramidal_tiff(img_small, "test_data/test_slide_small.tiff")
    
    # Also save as regular TIFF for comparison
    img_small.save("test_data/test_slide_regular.tiff")
    
    print("\nTest images created in test_data/:")
    for filename in os.listdir("test_data"):
        if filename.endswith(('.tiff', '.tif')):
            filepath = os.path.join("test_data", filename)
            size = os.path.getsize(filepath)
            print(f"  {filename}: {size:,} bytes")
    
    print("\nTo test:")
    print("1. Start backend: cd spinpath_web_ui/backend && python -m uvicorn main:app --reload")
    print("2. Upload one of the test images via the API or frontend")
    print("3. View in the image viewer component")

if __name__ == "__main__":
    main() 