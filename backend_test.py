import requests
import sys
import json
from datetime import datetime

class BackendAPITester:
    def __init__(self, base_url="https://601c0c19-6bbf-46b7-a807-4a3166f71907.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.workflow_contract_id = None
        self.run_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, check_response=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}" if endpoint else f"{self.api_url}/"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)

            print(f"   Status Code: {response.status_code}")
            
            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                
                # Additional response checks
                if check_response and response.status_code < 400:
                    try:
                        response_data = response.json()
                        check_result = check_response(response_data)
                        if not check_result:
                            success = False
                            self.tests_passed -= 1
                            print(f"❌ Failed - Response validation failed")
                        else:
                            print(f"✅ Response validation passed")
                    except Exception as e:
                        print(f"⚠️  Warning - Could not validate response: {e}")
                
                return success, response.json() if response.status_code < 400 else {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                if response.status_code >= 400:
                    try:
                        error_data = response.json()
                        print(f"   Error: {error_data}")
                    except:
                        print(f"   Error text: {response.text}")
                return False, {}

        except requests.exceptions.Timeout:
            print(f"❌ Failed - Request timeout")
            return False, {}
        except requests.exceptions.ConnectionError:
            print(f"❌ Failed - Connection error")
            return False, {}
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_root_endpoint(self):
        """Test GET /api/ should return { message: "Hello World" }"""
        def check_hello_world(response_data):
            return response_data.get("message") == "Hello World"
        
        success, response = self.run_test(
            "Root Endpoint",
            "GET",
            "",
            200,
            check_response=check_hello_world
        )
        return success

    def test_design_endpoint(self):
        """Test POST /api/design with goal should return workflow contract, fixture pack, assertion pack"""
        def check_design_response(response_data):
            # Check required keys exist
            required_keys = ["workflowContract", "fixturePack", "assertionPack"]
            for key in required_keys:
                if key not in response_data:
                    print(f"   Missing key: {key}")
                    return False
            
            # Check workflow contract has required fields
            wc = response_data["workflowContract"]
            if not wc.get("id") or not wc.get("name") or not wc.get("nodes"):
                print(f"   WorkflowContract missing required fields")
                return False
            
            # Store the workflow contract ID for later tests
            self.workflow_contract_id = wc["id"]
            print(f"   Workflow Contract ID: {self.workflow_contract_id}")
            
            return True
        
        success, response = self.run_test(
            "Design Endpoint",
            "POST",
            "design",
            200,
            data={"goal": "On POST {msg}, reply with uppercase msg"},
            check_response=check_design_response
        )
        return success

    def test_test_run_endpoint(self):
        """Test POST /api/test-run with workflow_contract_id should return run with PASS status"""
        if not self.workflow_contract_id:
            print("❌ Cannot test test-run without workflow_contract_id")
            return False
        
        def check_test_run_response(response_data):
            run = response_data.get("run")
            if not run:
                print("   Missing 'run' in response")
                return False
            
            # Check run has required fields
            if not run.get("id") or not run.get("status"):
                print("   Run missing required fields")
                return False
            
            # Store run ID for later test
            self.run_id = run["id"]
            print(f"   Run ID: {self.run_id}")
            print(f"   Run Status: {run['status']}")
            
            # Check status is PASS
            if run["status"] != "PASS":
                print(f"   Expected status PASS, got {run['status']}")
                return False
            
            # Check results array has at least 3 entries
            results = run.get("results", [])
            if len(results) < 3:
                print(f"   Expected at least 3 results, got {len(results)}")
                return False
            
            # Check junit_path exists
            if not run.get("junit_path"):
                print("   Missing junit_path")
                return False
            
            print(f"   Results count: {len(results)}")
            for i, result in enumerate(results):
                print(f"   Result {i+1}: {result.get('operator')} - {'PASS' if result.get('passed') else 'FAIL'}")
            
            return True
        
        success, response = self.run_test(
            "Test Run Endpoint",
            "POST",
            "test-run",
            200,
            data={"workflow_contract_id": self.workflow_contract_id},
            check_response=check_test_run_response
        )
        return success

    def test_get_run_endpoint(self):
        """Test GET /api/runs/{run_id} returns same run object"""
        if not self.run_id:
            print("❌ Cannot test get-run without run_id")
            return False
        
        def check_get_run_response(response_data):
            run = response_data.get("run")
            if not run:
                print("   Missing 'run' in response")
                return False
            
            # Check it's the same run ID
            if run.get("id") != self.run_id:
                print(f"   Expected run ID {self.run_id}, got {run.get('id')}")
                return False
            
            print(f"   Retrieved run ID: {run['id']}")
            print(f"   Run status: {run['status']}")
            
            return True
        
        success, response = self.run_test(
            "Get Run Endpoint",
            "GET",
            f"runs/{self.run_id}",
            200,
            check_response=check_get_run_response
        )
        return success

def main():
    print("🚀 Starting Backend API Tests")
    print("=" * 50)
    
    tester = BackendAPITester()
    
    # Test sequence as specified in the requirements
    tests = [
        ("Root Endpoint", tester.test_root_endpoint),
        ("Design Endpoint", tester.test_design_endpoint),
        ("Test Run Endpoint", tester.test_test_run_endpoint),
        ("Get Run Endpoint", tester.test_get_run_endpoint),
    ]
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            if not success:
                print(f"\n❌ {test_name} failed - stopping further tests")
                break
        except Exception as e:
            print(f"\n❌ {test_name} failed with exception: {e}")
            break
    
    # Print final results
    print("\n" + "=" * 50)
    print(f"📊 Backend API Test Results:")
    print(f"   Tests Run: {tester.tests_run}")
    print(f"   Tests Passed: {tester.tests_passed}")
    print(f"   Success Rate: {(tester.tests_passed/tester.tests_run*100):.1f}%" if tester.tests_run > 0 else "0%")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All backend tests passed!")
        return 0
    else:
        print("❌ Some backend tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())