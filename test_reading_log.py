#!/usr/bin/env python3
"""
Test script for reading log endpoints.
"""

import requests
import json
import sys
import argparse
from datetime import datetime


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_success(message: str):
    print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")


def print_error(message: str):
    print(f"{Colors.RED}✗ {message}{Colors.RESET}")


def print_info(message: str):
    print(f"{Colors.BLUE}ℹ {message}{Colors.RESET}")


def print_header(message: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{message}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")


def test_reading_log(base_url: str, access_token: str, shloka_id: str):
    """Test creating a reading log entry."""
    print_header("TEST: Create Reading Log")
    
    try:
        response = requests.post(
            f"{base_url}/api/reading-logs",
            json={
                "shloka_id": shloka_id,
                "reading_type": "summary"
            },
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            timeout=10
        )
        
        if response.status_code == 201:
            data = response.json()
            print_success("Reading log created successfully!")
            print_info(f"  Log ID: {data.get('data', {}).get('id', 'N/A')}")
            print_info(f"  Shloka ID: {data.get('data', {}).get('shloka', 'N/A')}")
            print_info(f"  Reading Type: {data.get('data', {}).get('reading_type', 'N/A')}")
            return True
        else:
            print_error(f"Failed with status {response.status_code}")
            try:
                error_data = response.json()
                print_error(f"Error: {json.dumps(error_data, indent=2)}")
            except:
                print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Request failed: {str(e)}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Test reading log endpoint")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL")
    parser.add_argument("--token", required=True, help="Access token")
    parser.add_argument("--shloka-id", required=True, help="Shloka ID to log")
    args = parser.parse_args()
    
    base_url = args.base_url.rstrip('/')
    
    print_header("READING LOG TEST")
    print_info(f"Testing API at: {base_url}")
    print_info(f"Shloka ID: {args.shloka_id}\n")
    
    success = test_reading_log(base_url, args.token, args.shloka_id)
    
    if success:
        print_success("\nAll tests passed!")
        sys.exit(0)
    else:
        print_error("\nTest failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()

