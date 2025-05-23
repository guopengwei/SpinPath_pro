#!/usr/bin/env python3
"""
Test script for SpinPath Web UI Backend
"""

import requests
import json
import time
from pathlib import Path

BASE_URL = "http://localhost:8000"

def test_health_check():
    """Test the health check endpoint"""
    print("Testing health check...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Health check status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

def test_root_endpoint():
    """Test the root endpoint"""
    print("\nTesting root endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"Root endpoint status: {response.status_code}")
        data = response.json()
        print(f"SpinPath status: {data.get('status')}")
        print(f"Available extractors: {data.get('available_extractors', [])}")
        return response.status_code == 200
    except Exception as e:
        print(f"Root endpoint test failed: {e}")
        return False

def test_models_endpoint():
    """Test the models endpoint"""
    print("\nTesting models endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/models")
        print(f"Models endpoint status: {response.status_code}")
        models = response.json()
        print(f"Available models: {len(models)}")
        for model in models:
            print(f"  - {model['name']} ({model['id']})")
        return response.status_code == 200
    except Exception as e:
        print(f"Models endpoint test failed: {e}")
        return False

def test_slides_endpoint():
    """Test the slides endpoint"""
    print("\nTesting slides endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/slides")
        print(f"Slides endpoint status: {response.status_code}")
        slides = response.json()
        print(f"Current slides: {len(slides)}")
        return response.status_code == 200
    except Exception as e:
        print(f"Slides endpoint test failed: {e}")
        return False

def test_file_upload():
    """Test file upload (creates a dummy file)"""
    print("\nTesting file upload...")
    try:
        # Create a dummy file for testing
        dummy_file_path = Path("test_slide.txt")
        dummy_file_path.write_text("This is a dummy slide file for testing")
        
        with open(dummy_file_path, 'rb') as f:
            files = {'file': ('test_slide.txt', f, 'text/plain')}
            response = requests.post(f"{BASE_URL}/slides", files=files)
        
        print(f"Upload status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Uploaded slide ID: {data['id']}")
            print(f"Filename: {data['filename']}")
            
            # Clean up
            dummy_file_path.unlink()
            return data['id']
        else:
            print(f"Upload failed: {response.text}")
            dummy_file_path.unlink()
            return None
    except Exception as e:
        print(f"File upload test failed: {e}")
        if dummy_file_path.exists():
            dummy_file_path.unlink()
        return None

def test_inference_creation(slide_id):
    """Test inference job creation"""
    print("\nTesting inference job creation...")
    try:
        payload = {
            "slide_ids": [slide_id],
            "model_id": "microsoft/ctranspath",
            "patch_size_um": 256.0,
            "num_workers": 1
        }
        
        response = requests.post(f"{BASE_URL}/inference", json=payload)
        print(f"Inference creation status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Job ID: {data['job_id']}")
            print(f"Status: {data['status']}")
            return data['job_id']
        else:
            print(f"Inference creation failed: {response.text}")
            return None
    except Exception as e:
        print(f"Inference creation test failed: {e}")
        return None

def test_job_status(job_id):
    """Test job status checking"""
    print(f"\nTesting job status for {job_id}...")
    try:
        response = requests.get(f"{BASE_URL}/inference/{job_id}")
        print(f"Job status check: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Job status: {data['status']}")
            print(f"Progress: {data.get('progress', 'N/A')}")
            return data
        else:
            print(f"Job status check failed: {response.text}")
            return None
    except Exception as e:
        print(f"Job status test failed: {e}")
        return None

def cleanup_slide(slide_id):
    """Clean up test slide"""
    print(f"\nCleaning up slide {slide_id}...")
    try:
        response = requests.delete(f"{BASE_URL}/slides/{slide_id}")
        print(f"Cleanup status: {response.status_code}")
        return response.status_code == 204
    except Exception as e:
        print(f"Cleanup failed: {e}")
        return False

def main():
    """Run all tests"""
    print("SpinPath Web UI Backend Test Suite")
    print("=" * 40)
    
    # Basic endpoint tests
    tests_passed = 0
    total_tests = 0
    
    total_tests += 1
    if test_health_check():
        tests_passed += 1
    
    total_tests += 1
    if test_root_endpoint():
        tests_passed += 1
    
    total_tests += 1
    if test_models_endpoint():
        tests_passed += 1
    
    total_tests += 1
    if test_slides_endpoint():
        tests_passed += 1
    
    # File upload test
    total_tests += 1
    slide_id = test_file_upload()
    if slide_id:
        tests_passed += 1
        
        # Inference test (only if upload succeeded)
        total_tests += 1
        job_id = test_inference_creation(slide_id)
        if job_id:
            tests_passed += 1
            
            # Job status test
            total_tests += 1
            if test_job_status(job_id):
                tests_passed += 1
        
        # Cleanup
        cleanup_slide(slide_id)
    
    print("\n" + "=" * 40)
    print(f"Test Results: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("✅ All tests passed! Backend is working correctly.")
    else:
        print("❌ Some tests failed. Check the output above for details.")
    
    return tests_passed == total_tests

if __name__ == "__main__":
    main() 