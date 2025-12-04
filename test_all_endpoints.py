#!/usr/bin/env python3
"""
Comprehensive integration test script for all Sanatan App endpoints.
Run this script to verify that all endpoints are working correctly.

Usage:
    python test_all_endpoints.py [--base-url BASE_URL]
    
Example:
    python test_all_endpoints.py --base-url http://localhost:8000
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


class TestRunner:
    """Test runner for all endpoints."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.access_token = None
        self.refresh_token = None
        self.user = None
        self.shloka_id = None
        self.conversation_id = None
        self.results = {}
    
    def test_health_check(self) -> bool:
        """Test health check endpoint."""
        print_info("Testing health check endpoint...")
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
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
    
    def test_signup(self) -> bool:
        """Test user signup."""
        print_header("TEST: User Signup")
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        test_email = f"test_{timestamp}@example.com"
        
        try:
            response = requests.post(
                f"{self.base_url}/api/auth/signup",
                json={
                    "name": "Test User",
                    "email": test_email,
                    "password": "testpass123",
                    "password_confirm": "testpass123"
                },
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 201:
                data = response.json()
                if data.get("data") and data["data"].get("tokens"):
                    self.user = data["data"]["user"]
                    self.access_token = data["data"]["tokens"]["access"]
                    self.refresh_token = data["data"]["tokens"]["refresh"]
                    print_success("Signup successful!")
                    return True
                else:
                    print_error("Signup response missing expected data")
                    return False
            else:
                print_error(f"Signup failed with status {response.status_code}")
                return False
        except Exception as e:
            print_error(f"Signup failed: {str(e)}")
            return False
    
    def test_login(self) -> bool:
        """Test user login."""
        print_header("TEST: User Login")
        if not self.user:
            print_warning("Skipping login test - no user created")
            return False
        
        try:
            response = requests.post(
                f"{self.base_url}/api/auth/login",
                json={
                    "email": self.user["email"],
                    "password": "testpass123"
                },
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("data") and data["data"].get("tokens"):
                    self.access_token = data["data"]["tokens"]["access"]
                    self.refresh_token = data["data"]["tokens"]["refresh"]
                    print_success("Login successful!")
                    return True
                else:
                    print_error("Login response missing expected data")
                    return False
            else:
                print_error(f"Login failed with status {response.status_code}")
                return False
        except Exception as e:
            print_error(f"Login failed: {str(e)}")
            return False
    
    def test_get_random_shloka(self) -> bool:
        """Test getting random shloka."""
        print_header("TEST: Get Random Shloka")
        if not self.access_token:
            print_warning("Skipping - no access token")
            return False
        
        try:
            response = requests.get(
                f"{self.base_url}/api/shlokas/random",
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("data") and data["data"].get("shloka"):
                    self.shloka_id = data["data"]["shloka"]["id"]
                    print_success(f"Got shloka: {data['data']['shloka']['book_name']}")
                    return True
                else:
                    print_error("Response missing shloka data")
                    return False
            else:
                print_error(f"Failed with status {response.status_code}")
                return False
        except Exception as e:
            print_error(f"Request failed: {str(e)}")
            return False
    
    def test_get_shloka_detail(self) -> bool:
        """Test getting shloka by ID."""
        print_header("TEST: Get Shloka Detail")
        if not self.access_token or not self.shloka_id:
            print_warning("Skipping - no access token or shloka ID")
            return False
        
        try:
            response = requests.get(
                f"{self.base_url}/api/shlokas/{self.shloka_id}",
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("data") and data["data"].get("shloka"):
                    print_success("Got shloka detail successfully")
                    return True
                else:
                    print_error("Response missing shloka data")
                    return False
            else:
                print_error(f"Failed with status {response.status_code}")
                return False
        except Exception as e:
            print_error(f"Request failed: {str(e)}")
            return False
    
    def test_create_reading_log(self) -> bool:
        """Test creating reading log."""
        print_header("TEST: Create Reading Log")
        if not self.access_token or not self.shloka_id:
            print_warning("Skipping - no access token or shloka ID")
            return False
        
        try:
            response = requests.post(
                f"{self.base_url}/api/reading-logs",
                json={
                    "shloka_id": self.shloka_id,
                    "reading_type": "summary"
                },
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json"
                },
                timeout=10
            )
            
            if response.status_code == 201:
                print_success("Reading log created successfully")
                return True
            else:
                print_error(f"Failed with status {response.status_code}")
                return False
        except Exception as e:
            print_error(f"Request failed: {str(e)}")
            return False
    
    def test_get_user_stats(self) -> bool:
        """Test getting user stats."""
        print_header("TEST: Get User Stats")
        if not self.access_token:
            print_warning("Skipping - no access token")
            return False
        
        try:
            response = requests.get(
                f"{self.base_url}/api/user/stats",
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("data"):
                    stats = data["data"]
                    print_success(f"Got stats - Level: {stats.get('level')}, XP: {stats.get('experience')}")
                    return True
                else:
                    print_error("Response missing stats data")
                    return False
            else:
                print_error(f"Failed with status {response.status_code}")
                return False
        except Exception as e:
            print_error(f"Request failed: {str(e)}")
            return False
    
    def test_favorites(self) -> bool:
        """Test favorites endpoints."""
        print_header("TEST: Favorites")
        if not self.access_token or not self.shloka_id:
            print_warning("Skipping - no access token or shloka ID")
            return False
        
        try:
            # Test adding favorite
            response = requests.post(
                f"{self.base_url}/api/favorites",
                json={"shloka_id": self.shloka_id},
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json"
                },
                timeout=10
            )
            
            if response.status_code not in [200, 201]:
                print_error(f"Add favorite failed with status {response.status_code}")
                return False
            
            print_success("Added favorite successfully")
            
            # Test listing favorites
            response = requests.get(
                f"{self.base_url}/api/favorites",
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                print_success(f"Listed favorites - count: {len(data.get('data', []))}")
            else:
                print_error(f"List favorites failed with status {response.status_code}")
                return False
            
            # Test deleting favorite
            response = requests.delete(
                f"{self.base_url}/api/favorites?shloka_id={self.shloka_id}",
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                print_success("Deleted favorite successfully")
                return True
            else:
                print_error(f"Delete favorite failed with status {response.status_code}")
                return False
        except Exception as e:
            print_error(f"Favorites test failed: {str(e)}")
            return False
    
    def test_achievements(self) -> bool:
        """Test achievements endpoint."""
        print_header("TEST: Achievements")
        if not self.access_token:
            print_warning("Skipping - no access token")
            return False
        
        try:
            response = requests.get(
                f"{self.base_url}/api/achievements",
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                print_success(f"Got achievements - count: {len(data.get('data', []))}")
                return True
            else:
                print_error(f"Failed with status {response.status_code}")
                return False
        except Exception as e:
            print_error(f"Request failed: {str(e)}")
            return False
    
    def test_chat_conversations(self) -> bool:
        """Test chat conversations endpoint."""
        print_header("TEST: Chat Conversations")
        if not self.access_token:
            print_warning("Skipping - no access token")
            return False
        
        try:
            response = requests.get(
                f"{self.base_url}/api/chat/conversations",
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                print_success(f"Got conversations - count: {len(data.get('data', []))}")
                if data.get('data') and len(data['data']) > 0:
                    self.conversation_id = data['data'][0]['id']
                return True
            else:
                print_error(f"Failed with status {response.status_code}")
                return False
        except Exception as e:
            print_error(f"Request failed: {str(e)}")
            return False
    
    def test_chat_message(self) -> bool:
        """Test sending chat message."""
        print_header("TEST: Send Chat Message")
        if not self.access_token:
            print_warning("Skipping - no access token")
            return False
        
        try:
            data = {"message": "What is the Bhagavad Gita?"}
            if self.conversation_id:
                data["conversation_id"] = self.conversation_id
            
            response = requests.post(
                f"{self.base_url}/api/chat/message",
                json=data,
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json"
                },
                timeout=30  # Chat might take longer
            )
            
            if response.status_code == 200:
                print_success("Chat message sent successfully")
                return True
            elif response.status_code == 500:
                print_warning("Chat message failed - might be missing GROQ_API_KEY")
                return False
            else:
                print_error(f"Failed with status {response.status_code}")
                return False
        except Exception as e:
            print_error(f"Request failed: {str(e)}")
            return False
    
    def run_all_tests(self):
        """Run all tests."""
        print_header("COMPREHENSIVE API TEST SUITE")
        print_info(f"Testing API at: {self.base_url}")
        print_info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Health check first
        if not self.test_health_check():
            print_error("\nHealth check failed. Is the server running?")
            return False
        
        # Run tests in order
        tests = [
            ("Signup", self.test_signup),
            ("Login", self.test_login),
            ("Get Random Shloka", self.test_get_random_shloka),
            ("Get Shloka Detail", self.test_get_shloka_detail),
            ("Create Reading Log", self.test_create_reading_log),
            ("Get User Stats", self.test_get_user_stats),
            ("Favorites", self.test_favorites),
            ("Achievements", self.test_achievements),
            ("Chat Conversations", self.test_chat_conversations),
            ("Chat Message", self.test_chat_message),
        ]
        
        for test_name, test_func in tests:
            try:
                self.results[test_name] = test_func()
            except Exception as e:
                print_error(f"Test {test_name} crashed: {str(e)}")
                self.results[test_name] = False
        
        # Print summary
        print_header("TEST SUMMARY")
        total_tests = len(self.results)
        passed_tests = sum(1 for v in self.results.values() if v)
        
        for test_name, passed in self.results.items():
            status = "PASS" if passed else "FAIL"
            color = Colors.GREEN if passed else Colors.RED
            print(f"{color}{'✓' if passed else '✗'}{Colors.RESET} {test_name}: {status}")
        
        print(f"\n{Colors.BOLD}Total: {passed_tests}/{total_tests} tests passed{Colors.RESET}\n")
        
        return passed_tests == total_tests


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Test all API endpoints")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)"
    )
    args = parser.parse_args()
    
    runner = TestRunner(args.base_url)
    success = runner.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

