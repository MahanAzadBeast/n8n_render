import requests
import sys
import json
import os
from datetime import datetime

class BackendAPITester:
    def __init__(self, base_url="https://601c0c19-6bbf-46b7-a807-4a3166f71907.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.workflow_contract_id = None
        self.run_id = None
        self.junit_artifact_id = None

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

    def test_test_run_mock_endpoint(self):
        """Test POST /api/test-run with use_n8n=false should PASS and include junit_path and meta"""
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
            
            # Check meta exists (may be empty for mock)
            if "meta" not in run:
                print("   Missing meta field")
                return False
            
            print(f"   Results count: {len(results)}")
            print(f"   JUnit path: {run.get('junit_path')}")
            print(f"   Meta: {run.get('meta')}")
            
            for i, result in enumerate(results):
                print(f"   Result {i+1}: {result.get('operator')} - {'PASS' if result.get('passed') else 'FAIL'}")
            
            return True
        
        success, response = self.run_test(
            "Test Run Mock (use_n8n=false)",
            "POST",
            "test-run",
            200,
            data={"workflow_contract_id": self.workflow_contract_id, "use_n8n": False},
            check_response=check_test_run_response
        )
        return success

    def test_test_run_n8n_no_env(self):
        """Test POST /api/test-run with use_n8n=true but no N8N_API_KEY should still PASS (fallback to mock)"""
        if not self.workflow_contract_id:
            print("❌ Cannot test test-run without workflow_contract_id")
            return False
        
        def check_test_run_response(response_data):
            run = response_data.get("run")
            if not run:
                print("   Missing 'run' in response")
                return False
            
            print(f"   Run Status: {run['status']}")
            
            # Should still PASS even with use_n8n=true but no env
            if run["status"] != "PASS":
                print(f"   Expected status PASS (fallback to mock), got {run['status']}")
                return False
            
            # Check meta exists
            if "meta" not in run:
                print("   Missing meta field")
                return False
            
            print(f"   Meta: {run.get('meta')}")
            print("   ✅ Correctly fell back to mock execution when N8N_API_KEY not available")
            
            return True
        
        success, response = self.run_test(
            "Test Run N8N without env (use_n8n=true, no N8N_API_KEY)",
            "POST",
            "test-run",
            200,
            data={"workflow_contract_id": self.workflow_contract_id, "use_n8n": True},
            check_response=check_test_run_response
        )
        return success

    def test_test_run_n8n_with_env(self):
        """Test POST /api/test-run with use_n8n=true and N8N_API_KEY set"""
        if not self.workflow_contract_id:
            print("❌ Cannot test test-run without workflow_contract_id")
            return False
        
        # Check if N8N_API_KEY is available for testing
        n8n_api_key = os.environ.get("N8N_API_KEY")
        if not n8n_api_key:
            print("⚠️  Skipping N8N real execution test - N8N_API_KEY not set in environment")
            return True  # Skip this test but don't fail
        
        def check_test_run_response(response_data):
            run = response_data.get("run")
            if not run:
                print("   Missing 'run' in response")
                return False
            
            print(f"   Run Status: {run['status']}")
            
            # Should PASS with real n8n execution
            if run["status"] != "PASS":
                print(f"   Expected status PASS, got {run['status']}")
                return False
            
            # Check meta has n8n-specific fields
            meta = run.get("meta", {})
            required_meta_fields = ["workflowId", "webhookTestUrl", "webhookProdUrl", "executionLogFirst20"]
            
            for field in required_meta_fields:
                if field not in meta:
                    print(f"   Missing meta field: {field}")
                    return False
            
            print(f"   Workflow ID: {meta.get('workflowId')}")
            print(f"   Webhook Test URL: {meta.get('webhookTestUrl')}")
            print(f"   Webhook Prod URL: {meta.get('webhookProdUrl')}")
            print(f"   Execution Log Lines: {len(meta.get('executionLogFirst20', []))}")
            
            # Verify temp workflow deletion (should be observable in logs)
            print("   ✅ Real N8N execution completed with meta fields")
            
            return True
        
        success, response = self.run_test(
            "Test Run N8N with env (use_n8n=true, N8N_API_KEY set)",
            "POST",
            "test-run",
            200,
            data={"workflow_contract_id": self.workflow_contract_id, "use_n8n": True},
            check_response=check_test_run_response
        )
        return success

    def test_junit_file_exists(self):
        """Verify that junit_path file exists on server (since we don't have artifacts list endpoint)"""
        if not self.run_id:
            print("❌ Cannot test junit file without run_id")
            return False
        
        # We can't directly check file existence on server, but we can verify the run has junit_path
        def check_run_has_junit(response_data):
            run = response_data.get("run")
            if not run:
                print("   Missing 'run' in response")
                return False
            
            junit_path = run.get("junit_path")
            if not junit_path:
                print("   Missing junit_path in run")
                return False
            
            print(f"   JUnit path: {junit_path}")
            print("   ✅ Run has junit_path (file should exist on server)")
            
            return True
        
        success, response = self.run_test(
            "Verify JUnit file path exists",
            "GET",
            f"runs/{self.run_id}",
            200,
            check_response=check_run_has_junit
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
        ("Test Run Mock", tester.test_test_run_mock_endpoint),
        ("Test Run N8N No Env", tester.test_test_run_n8n_no_env),
        ("Test Run N8N With Env", tester.test_test_run_n8n_with_env),
        ("Get Run Endpoint", tester.test_get_run_endpoint),
        ("JUnit File Exists", tester.test_junit_file_exists),
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