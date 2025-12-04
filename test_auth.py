#!/usr/bin/env python3
"""
Test script for authentication endpoints.
Run this script to verify that authentication is working correctly.

Usage:
    python test_auth.py [--base-url BASE_URL]
    
Example:
    python test_auth.py --base-url http://localhost:8000
"""

import requests
import json
import sys
import argparse
from datetime import datetime
from typing import Dict, Optional, Tuple


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_success(message: str):
    """Print success message in green."""
    print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")


def print_error(message: str):
    """Print error message in red."""
    print(f"{Colors.RED}✗ {message}{Colors.RESET}")


def print_info(message: str):
    """Print info message in blue."""
    print(f"{Colors.BLUE}ℹ {message}{Colors.RESET}")


def print_warning(message: str):
    """Print warning message in yellow."""
    print(f"{Colors.YELLOW}⚠ {message}{Colors.RESET}")


def print_header(message: str):
    """Print header message."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{message}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")


def test_health_check(base_url: str) -> bool:
    """Test health check endpoint."""
    print_info("Testing health check endpoint...")
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print_success(f"Health check passed: {data.get('message', 'OK')}")
            return True
        else:
            print_error(f"Health check failed with status {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Health check failed: {str(e)}")
        return False


def test_signup(base_url: str) -> Optional[Tuple[Dict, str, str]]:
    """Test user signup endpoint."""
    print_header("TEST 1: User Signup")
    
    # Generate unique email based on timestamp
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    test_email = f"test_{timestamp}@example.com"
    test_name = "Test User"
    test_password = "testpassword123"
    
    print_info(f"Signing up user: {test_email}")
    
    try:
        response = requests.post(
            f"{base_url}/api/auth/signup",
            json={
                "name": test_name,
                "email": test_email,
                "password": test_password,
                "password_confirm": test_password
            },
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 201:
            data = response.json()
            if data.get("data") and data["data"].get("user") and data["data"].get("tokens"):
                user = data["data"]["user"]
                tokens = data["data"]["tokens"]
                print_success(f"Signup successful!")
                print_info(f"  User ID: {user.get('id')}")
                print_info(f"  Name: {user.get('name')}")
                print_info(f"  Email: {user.get('email')}")
                print_info(f"  Access token: {tokens.get('access')[:50]}...")
                print_info(f"  Refresh token: {tokens.get('refresh')[:50]}...")
                return (user, tokens["access"], tokens["refresh"])
            else:
                print_error("Signup response missing expected data")
                print_error(f"Response: {json.dumps(data, indent=2)}")
                return None
        else:
            print_error(f"Signup failed with status {response.status_code}")
            try:
                error_data = response.json()
                print_error(f"Error: {json.dumps(error_data, indent=2)}")
            except:
                print_error(f"Response: {response.text}")
            return None
    except Exception as e:
        print_error(f"Signup request failed: {str(e)}")
        return None


def test_login(base_url: str, email: str, password: str) -> Optional[Tuple[str, str]]:
    """Test user login endpoint."""
    print_header("TEST 2: User Login")
    
    print_info(f"Logging in user: {email}")
    
    try:
        response = requests.post(
            f"{base_url}/api/auth/login",
            json={
                "email": email,
                "password": password
            },
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("data") and data["data"].get("tokens"):
                tokens = data["data"]["tokens"]
                print_success("Login successful!")
                print_info(f"  Access token: {tokens.get('access')[:50]}...")
                print_info(f"  Refresh token: {tokens.get('refresh')[:50]}...")
                return (tokens["access"], tokens["refresh"])
            else:
                print_error("Login response missing expected data")
                print_error(f"Response: {json.dumps(data, indent=2)}")
                return None
        else:
            print_error(f"Login failed with status {response.status_code}")
            try:
                error_data = response.json()
                print_error(f"Error: {json.dumps(error_data, indent=2)}")
            except:
                print_error(f"Response: {response.text}")
            return None
    except Exception as e:
        print_error(f"Login request failed: {str(e)}")
        return None


def test_token_refresh(base_url: str, refresh_token: str) -> Optional[str]:
    """Test token refresh endpoint."""
    print_header("TEST 3: Token Refresh")
    
    print_info("Refreshing access token...")
    
    try:
        response = requests.post(
            f"{base_url}/api/auth/refresh",
            json={
                "refresh": refresh_token
            },
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("data") and data["data"].get("access"):
                new_access_token = data["data"]["access"]
                new_refresh_token = data["data"].get("refresh")
                print_success("Token refresh successful!")
                print_info(f"  New access token: {new_access_token[:50]}...")
                if new_refresh_token:
                    print_info(f"  New refresh token: {new_refresh_token[:50]}... (rotation enabled)")
                else:
                    print_info("  Refresh token unchanged (rotation disabled)")
                return new_access_token
            else:
                print_error("Token refresh response missing expected data")
                print_error(f"Response: {json.dumps(data, indent=2)}")
                return None
        else:
            print_error(f"Token refresh failed with status {response.status_code}")
            try:
                error_data = response.json()
                print_error(f"Error: {json.dumps(error_data, indent=2)}")
            except:
                print_error(f"Response: {response.text}")
            return None
    except Exception as e:
        print_error(f"Token refresh request failed: {str(e)}")
        return None


def test_authenticated_endpoint(base_url: str, access_token: str) -> bool:
    """Test an authenticated endpoint (random shloka)."""
    print_header("TEST 4: Authenticated Endpoint")
    
    print_info("Fetching random shloka with access token...")
    
    try:
        response = requests.get(
            f"{base_url}/api/shlokas/random",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("data") and data["data"].get("shloka"):
                shloka = data["data"]["shloka"]
                print_success("Authenticated request successful!")
                print_info(f"  Shloka ID: {shloka.get('id')}")
                print_info(f"  Book: {shloka.get('book_name')}")
                print_info(f"  Chapter: {shloka.get('chapter_number')}, Verse: {shloka.get('verse_number')}")
                return True
            else:
                print_error("Response missing shloka data")
                print_error(f"Response: {json.dumps(data, indent=2)}")
                return False
        elif response.status_code == 401:
            print_error("Authentication failed - token may be invalid or expired")
            try:
                error_data = response.json()
                print_error(f"Error: {json.dumps(error_data, indent=2)}")
            except:
                print_error(f"Response: {response.text}")
            return False
        else:
            print_error(f"Request failed with status {response.status_code}")
            try:
                error_data = response.json()
                print_error(f"Error: {json.dumps(error_data, indent=2)}")
            except:
                print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Authenticated request failed: {str(e)}")
        return False


def test_invalid_credentials(base_url: str) -> bool:
    """Test login with invalid credentials."""
    print_header("TEST 5: Invalid Credentials")
    
    print_info("Testing login with invalid credentials...")
    
    try:
        response = requests.post(
            f"{base_url}/api/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "wrongpassword"
            },
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 401:
            print_success("Correctly rejected invalid credentials (401)")
            return True
        else:
            print_warning(f"Expected 401, got {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Test failed: {str(e)}")
        return False


def main():
    """Run all authentication tests."""
    parser = argparse.ArgumentParser(description="Test authentication endpoints")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)"
    )
    args = parser.parse_args()
    
    base_url = args.base_url.rstrip('/')
    
    print_header("AUTHENTICATION TEST SUITE")
    print_info(f"Testing API at: {base_url}")
    print_info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Test health check first
    if not test_health_check(base_url):
        print_error("\nHealth check failed. Is the server running?")
        sys.exit(1)
    
    results = {
        "signup": False,
        "login": False,
        "token_refresh": False,
        "authenticated_endpoint": False,
        "invalid_credentials": False
    }
    
    # Test signup
    signup_result = test_signup(base_url)
    if signup_result:
        user, access_token, refresh_token = signup_result
        results["signup"] = True
        test_email = user["email"]
        test_password = "testpassword123"  # We know this from signup
        
        # Test login
        login_result = test_login(base_url, test_email, test_password)
        if login_result:
            results["login"] = True
            access_token, refresh_token = login_result
            
            # Test token refresh
            new_access_token = test_token_refresh(base_url, refresh_token)
            if new_access_token:
                results["token_refresh"] = True
                access_token = new_access_token
            
            # Test authenticated endpoint
            if test_authenticated_endpoint(base_url, access_token):
                results["authenticated_endpoint"] = True
    else:
        print_warning("Skipping remaining tests due to signup failure")
    
    # Test invalid credentials
    results["invalid_credentials"] = test_invalid_credentials(base_url)
    
    # Print summary
    print_header("TEST SUMMARY")
    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)
    
    for test_name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        color = Colors.GREEN if passed else Colors.RED
        print(f"{color}{'✓' if passed else '✗'}{Colors.RESET} {test_name.replace('_', ' ').title()}: {status}")
    
    print(f"\n{Colors.BOLD}Total: {passed_tests}/{total_tests} tests passed{Colors.RESET}\n")
    
    if passed_tests == total_tests:
        print_success("All tests passed! Authentication is working correctly.")
        sys.exit(0)
    else:
        print_error("Some tests failed. Please check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()

