#!/usr/bin/env python3
"""
NO2 Pollution Map Viewer - Backend API Testing
Tests all authentication and analysis endpoints with Socket.IO integration
"""

import requests
import sys
import json
import time
from datetime import datetime, timedelta

class NO2BackendTester:
    def __init__(self, base_url="https://tropospheric-view.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}")
        else:
            print(f"❌ {name} - {details}")
        
        self.test_results.append({
            "test": name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        
        if self.token:
            test_headers['Authorization'] = f'Bearer {self.token}'
        if headers:
            test_headers.update(headers)

        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=test_headers, timeout=10)

            success = response.status_code == expected_status
            details = f"Status: {response.status_code}"
            
            if not success:
                details += f" (Expected: {expected_status})"
                try:
                    error_data = response.json()
                    if 'detail' in error_data:
                        details += f" - {error_data['detail']}"
                except:
                    details += f" - {response.text[:100]}"

            self.log_test(name, success, details)
            
            if success:
                try:
                    return response.json()
                except:
                    return {"status": "success"}
            return None

        except Exception as e:
            self.log_test(name, False, f"Error: {str(e)}")
            return None

    def test_auth_endpoints(self):
        """Test authentication endpoints"""
        print("\n🔐 Testing Authentication Endpoints...")
        
        # Test login with correct credentials
        login_data = {
            "email": "sarvesh_pc",
            "password": "sarvesh_pc@06"
        }
        
        response = self.run_test(
            "Login with valid credentials",
            "POST",
            "auth/login",
            200,
            data=login_data
        )
        
        if response and 'token' in response:
            self.token = response['token']
            print(f"   Token obtained: {self.token[:20]}...")
        else:
            print("   ❌ Failed to get token from login response")
            return False

        # Test login with wrong credentials
        wrong_login = {
            "email": "wrong_user",
            "password": "wrong_pass"
        }
        
        self.run_test(
            "Login with invalid credentials",
            "POST",
            "auth/login",
            401,
            data=wrong_login
        )

        # Test /auth/me endpoint
        self.run_test(
            "Get current user info",
            "GET",
            "auth/me",
            200
        )

        # Test logout
        self.run_test(
            "Logout",
            "POST",
            "auth/logout",
            200
        )

        return True

    def test_analysis_endpoints(self):
        """Test analysis endpoints"""
        print("\n🔬 Testing Analysis Endpoints...")
        
        # Test polygon for analysis
        test_polygon = {
            "type": "Polygon",
            "coordinates": [[
                [77.0, 20.0],
                [78.0, 20.0],
                [78.0, 21.0],
                [77.0, 21.0],
                [77.0, 20.0]
            ]]
        }
        
        # Test start analysis
        analysis_data = {
            "polygon": test_polygon,
            "date": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        }
        
        analysis_response = self.run_test(
            "Start analysis",
            "POST",
            "analysis/start",
            200,
            data=analysis_data
        )
        
        analysis_id = None
        if analysis_response and 'analysis_id' in analysis_response:
            analysis_id = analysis_response['analysis_id']
            print(f"   Analysis ID: {analysis_id}")
            
            # Wait a moment for analysis to start
            time.sleep(2)
            
            # Test get specific analysis
            self.run_test(
                "Get analysis by ID",
                "GET",
                f"analysis/{analysis_id}",
                200
            )
            
            # Wait for analysis to potentially complete
            print("   Waiting for analysis pipeline to process...")
            time.sleep(8)  # Give time for the 4 agents to run
            
            # Check analysis status again
            final_response = self.run_test(
                "Get completed analysis",
                "GET",
                f"analysis/{analysis_id}",
                200
            )
            
            if final_response:
                status = final_response.get('status', 'unknown')
                print(f"   Final analysis status: {status}")
                
                # Check if all agents completed
                agents = final_response.get('agents', {})
                completed_agents = [k for k, v in agents.items() if v == 'complete']
                print(f"   Completed agents: {len(completed_agents)}/4")
                
                # Check if data was generated
                has_data = all(key in final_response for key in ['no2_data', 'statistics', 'trend_data', 'recommendations'])
                self.log_test("Analysis generated all required data", has_data, 
                            f"Missing: {[k for k in ['no2_data', 'statistics', 'trend_data', 'recommendations'] if k not in final_response]}")

        # Test get all analyses
        self.run_test(
            "Get user analyses list",
            "GET",
            "analyses",
            200
        )

        return analysis_id

    def test_unauthorized_access(self):
        """Test endpoints without authentication"""
        print("\n🚫 Testing Unauthorized Access...")
        
        # Temporarily remove token
        original_token = self.token
        self.token = None
        
        self.run_test(
            "Access /auth/me without token",
            "GET",
            "auth/me",
            401
        )
        
        self.run_test(
            "Start analysis without token",
            "POST",
            "analysis/start",
            401,
            data={"polygon": {}, "date": "2024-01-01"}
        )
        
        # Restore token
        self.token = original_token

    def test_edge_cases(self):
        """Test edge cases and error handling"""
        print("\n⚠️  Testing Edge Cases...")
        
        # Test invalid polygon
        invalid_analysis = {
            "polygon": {"type": "Invalid"},
            "date": "2024-01-01"
        }
        
        self.run_test(
            "Start analysis with invalid polygon",
            "POST",
            "analysis/start",
            500,  # Might be 400 or 422 depending on validation
            data=invalid_analysis
        )
        
        # Test non-existent analysis
        self.run_test(
            "Get non-existent analysis",
            "GET",
            "analysis/non-existent-id",
            404
        )

    def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting NO2 Pollution Map Viewer Backend Tests")
        print(f"Testing against: {self.base_url}")
        print("=" * 60)
        
        # Test authentication first
        if not self.test_auth_endpoints():
            print("❌ Authentication tests failed. Stopping.")
            return False
        
        # Test analysis endpoints
        analysis_id = self.test_analysis_endpoints()
        
        # Test unauthorized access
        self.test_unauthorized_access()
        
        # Test edge cases
        self.test_edge_cases()
        
        # Print summary
        print("\n" + "=" * 60)
        print(f"📊 Test Summary: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return True
        else:
            print(f"❌ {self.tests_run - self.tests_passed} tests failed")
            return False

def main():
    """Main test runner"""
    tester = NO2BackendTester()
    success = tester.run_all_tests()
    
    # Save test results
    with open('/app/test_reports/backend_test_results.json', 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'total_tests': tester.tests_run,
            'passed_tests': tester.tests_passed,
            'success_rate': tester.tests_passed / tester.tests_run if tester.tests_run > 0 else 0,
            'results': tester.test_results
        }, f, indent=2)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())