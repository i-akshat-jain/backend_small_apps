#!/usr/bin/env python
"""
Test script to verify Celery setup is working correctly.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.sanatan_app.tasks import test_task
import time

def main():
    print("=" * 60)
    print("Testing Celery Setup")
    print("=" * 60)
    
    # Test 1: Check if task can be called synchronously
    print("\n1. Testing synchronous task execution...")
    try:
        result = test_task("Synchronous test")
        print(f"   ✓ Synchronous execution successful: {result}")
    except Exception as e:
        print(f"   ✗ Synchronous execution failed: {e}")
        return False
    
    # Test 2: Check if task can be called asynchronously
    print("\n2. Testing asynchronous task execution...")
    try:
        async_result = test_task.delay("Asynchronous test")
        print(f"   ✓ Task submitted to queue. Task ID: {async_result.id}")
        
        # Wait for task to complete (with timeout)
        print("   Waiting for task to complete...")
        timeout = 10  # seconds
        start_time = time.time()
        
        while not async_result.ready():
            if time.time() - start_time > timeout:
                print(f"   ✗ Task timed out after {timeout} seconds")
                print(f"   Task state: {async_result.state}")
                return False
            time.sleep(0.5)
        
        result = async_result.get(timeout=5)
        print(f"   ✓ Task completed successfully: {result}")
        print(f"   Task state: {async_result.state}")
        
    except Exception as e:
        print(f"   ✗ Asynchronous execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("✓ All Celery tests passed!")
    print("=" * 60)
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)

