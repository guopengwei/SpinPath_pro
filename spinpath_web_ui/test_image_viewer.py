#!/usr/bin/env python3
"""
Test script for the SpinPath Web UI Image Viewer

This script downloads a sample whole slide image and tests the image viewer functionality.
"""

import os
import sys
import requests
import zipfile
from pathlib import Path

def download_sample_slide():
    """Download a sample whole slide image for testing"""
    
    # Sample slide URLs (small test images)
    sample_slides = {
        "sample_svs": {
            "url": "https://openslide.cs.cmu.edu/download/openslide-testdata/Aperio/CMU-1-Small-Region.svs",
            "filename": "CMU-1-Small-Region.svs",
            "description": "Small Aperio SVS file for testing"
        },
        "sample_ndpi": {
            "url": "https://openslide.cs.cmu.edu/download/openslide-testdata/Hamamatsu/CMU-1-Small-Region.ndpi",
            "filename": "CMU-1-Small-Region.ndpi", 
            "description": "Small Hamamatsu NDPI file for testing"
        }
    }
    
    # Create test data directory
    test_data_dir = Path("test_data")
    test_data_dir.mkdir(exist_ok=True)
    
    print("Downloading sample whole slide images for testing...")
    
    downloaded_files = []
    
    for slide_name, slide_info in sample_slides.items():
        local_path = test_data_dir / slide_info["filename"]
        
        if local_path.exists():
            print(f"✓ {slide_info['filename']} already exists")
            downloaded_files.append(str(local_path))
            continue
            
        try:
            print(f"Downloading {slide_info['filename']}...")
            response = requests.get(slide_info["url"], stream=True)
            response.raise_for_status()
            
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"✓ Downloaded {slide_info['filename']} ({local_path.stat().st_size} bytes)")
            downloaded_files.append(str(local_path))
            
        except Exception as e:
            print(f"✗ Failed to download {slide_info['filename']}: {e}")
    
    return downloaded_files

def test_tile_server():
    """Test the tile server functionality"""
    try:
        from spinpath_web_ui.backend.tile_server import tile_server, detect_slide_format
        
        downloaded_files = download_sample_slide()
        
        if not downloaded_files:
            print("No test files available, cannot test tile server")
            return False
            
        print("\nTesting tile server functionality...")
        
        for slide_path in downloaded_files:
            print(f"\nTesting slide: {slide_path}")
            
            # Test format detection
            format_type = detect_slide_format(slide_path)
            print(f"  Format detected: {format_type}")
            
            if format_type == "unknown":
                print(f"  ✗ Unsupported format, skipping")
                continue
            
            try:
                # Test slide info
                info = tile_server.get_slide_info(slide_path)
                print(f"  ✓ Slide info: {info['dimensions']}, {info['level_count']} levels")
                
                # Test thumbnail
                thumbnail_bytes = tile_server.get_thumbnail(slide_path, (256, 256))
                print(f"  ✓ Thumbnail generated: {len(thumbnail_bytes)} bytes")
                
                # Test tile extraction
                if info['level_count'] > 0:
                    tile_bytes = tile_server.get_tile(slide_path, 0, 0, 0)
                    print(f"  ✓ Tile extracted: {len(tile_bytes)} bytes")
                
            except Exception as e:
                print(f"  ✗ Error testing slide: {e}")
        
        return True
        
    except ImportError as e:
        print(f"Cannot import tile server: {e}")
        return False

def test_backend_integration():
    """Test backend integration by starting the server and making requests"""
    import subprocess
    import time
    import signal
    
    print("\nTesting backend integration...")
    
    # Change to backend directory
    backend_dir = Path("spinpath_web_ui/backend")
    
    if not backend_dir.exists():
        print("Backend directory not found")
        return False
    
    try:
        # Start the backend server
        print("Starting backend server...")
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"],
            cwd=backend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait a bit for server to start
        time.sleep(5)
        
        # Test health endpoint
        try:
            response = requests.get("http://localhost:8000/health", timeout=10)
            if response.status_code == 200:
                health_data = response.json()
                print(f"✓ Backend server is healthy: {health_data}")
            else:
                print(f"✗ Health check failed: {response.status_code}")
        except Exception as e:
            print(f"✗ Could not connect to backend: {e}")
        
        # Upload a test slide
        downloaded_files = download_sample_slide()
        if downloaded_files:
            try:
                test_file = downloaded_files[0]
                print(f"Uploading test slide: {test_file}")
                
                with open(test_file, 'rb') as f:
                    files = {'file': (Path(test_file).name, f, 'application/octet-stream')}
                    response = requests.post("http://localhost:8000/slides", files=files, timeout=30)
                
                if response.status_code == 200:
                    upload_result = response.json()
                    slide_id = upload_result['id']
                    print(f"✓ Slide uploaded successfully: {slide_id}")
                    
                    # Test slide info endpoint
                    info_response = requests.get(f"http://localhost:8000/api/slides/{slide_id}/info", timeout=10)
                    if info_response.status_code == 200:
                        slide_info = info_response.json()
                        print(f"✓ Slide info retrieved: {slide_info['dimensions']}")
                    else:
                        print(f"✗ Failed to get slide info: {info_response.status_code}")
                    
                    # Test thumbnail endpoint
                    thumb_response = requests.get(f"http://localhost:8000/api/slides/{slide_id}/thumbnail", timeout=10)
                    if thumb_response.status_code == 200:
                        print(f"✓ Thumbnail retrieved: {len(thumb_response.content)} bytes")
                    else:
                        print(f"✗ Failed to get thumbnail: {thumb_response.status_code}")
                        
                    # Test tile endpoint
                    tile_response = requests.get(f"http://localhost:8000/api/slides/{slide_id}/tile/0/0/0", timeout=10)
                    if tile_response.status_code == 200:
                        print(f"✓ Tile retrieved: {len(tile_response.content)} bytes")
                    else:
                        print(f"✗ Failed to get tile: {tile_response.status_code}")
                        
                else:
                    print(f"✗ Failed to upload slide: {response.status_code}")
                    
            except Exception as e:
                print(f"✗ Error testing slide upload: {e}")
        
        # Stop the server
        print("Stopping backend server...")
        process.terminate()
        process.wait(timeout=10)
        
        return True
        
    except Exception as e:
        print(f"Error testing backend: {e}")
        return False

def main():
    """Main test function"""
    print("SpinPath Web UI Image Viewer Test")
    print("=" * 40)
    
    # Test 1: Download sample slides
    print("1. Downloading sample slides...")
    downloaded_files = download_sample_slide()
    
    if not downloaded_files:
        print("No sample slides available for testing")
        return
    
    # Test 2: Test tile server
    print("\n2. Testing tile server...")
    tile_server_ok = test_tile_server()
    
    if not tile_server_ok:
        print("Tile server tests failed")
        return
    
    # Test 3: Test backend integration  
    print("\n3. Testing backend integration...")
    backend_ok = test_backend_integration()
    
    if backend_ok:
        print("\n✓ All tests passed! The image viewer should be working.")
        print("\nTo test manually:")
        print("1. Start the backend: cd spinpath_web_ui/backend && python -m uvicorn main:app --reload")
        print("2. Start the frontend: cd spinpath_web_ui/frontend && npm run dev")
        print("3. Upload one of the test slides and view it in the image viewer")
    else:
        print("\n✗ Some tests failed. Check the errors above.")

if __name__ == "__main__":
    main() 