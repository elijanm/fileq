import pytest
import os
import sys
from datetime import datetime, timezone
import uuid
from unittest.mock import patch, Mock
import requests
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Import the lago service
from services.lago_billing import *

# Test configuration
TEST_CUSTOMER_ID = f"test_customer_{uuid.uuid4().hex[:8]}"
TEST_PLAN_CODE = f"another_plan"
TEST_METRIC_CODE = f"test_metric_{uuid.uuid4().hex[:8]}"
TEST_COUPON_CODE = f"test_coupon_{uuid.uuid4().hex[:8]}"
TEST_ADD_ON_CODE = f"test_addon_{uuid.uuid4().hex[:8]}"
TEST_TAX_CODE = f"test_tax_{uuid.uuid4().hex[:8]}"

# Global variables to store IDs for dependent tests
created_customer_id="710f850b"
created_subscription_id = None
created_plan_code = None
created_metric_code = "5625f0e5"
created_invoice_id = None
created_wallet_id = None
created_coupon_code = None
created_add_on_code = None
created_tax_code = None


class TestLagoService:
    """Test suite for Lago API service"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup before each test"""
        # Ensure environment variables are set
        if not os.getenv("LAGO_API_URL"):
            os.environ["LAGO_API_URL"] = "http://95.110.228.29:8724"
        if not os.getenv("LAGO_API_KEY"):
            os.environ["LAGO_API_KEY"] = "135b2387-0d51-4099-ad96-82e86ecf6ae8"

    def test_health_check(self):
        """Test health check endpoint"""
        try:
            result = health_check()
            print(f"✓ Health check: {result}")
        except requests.exceptions.RequestException as e:
            print(f"✗ Health check failed: {e}")
            pytest.skip("Lago API is not available")

    # ==============================================================================
    # CUSTOMER TESTS
    # ==============================================================================

    def test_create_customer(self):
        """Test customer creation"""
        global created_customer_id
        try:
            result = create_customer(
                external_id=TEST_CUSTOMER_ID,
                email=f"{TEST_CUSTOMER_ID}@example.com",
                name=f"Test Customer {TEST_CUSTOMER_ID}",
                currency="USD",
                country="US"
            )
            created_customer_id = TEST_CUSTOMER_ID
            print(f"✓ Customer created: {result.get('customer', {}).get('external_id')}")
        except Exception as e:
            print(f"✗ Customer creation failed: {e}")
            raise

    def test_get_customer(self):
        """Test getting customer"""
        
        if not created_customer_id:
            pytest.skip("No customer created")
        
        try:
            result = get_customer(created_customer_id)
            print(f"✓ Customer retrieved: {result.get('customer', {}).get('name')}")
        except Exception as e:
            print(f"✗ Get customer failed: {e}")
            raise

    def test_list_customers(self):
        """Test listing customers"""
        try:
            result = list_customers(page=1, per_page=5)
            print(result)
            print(f"✓ Customers listed: {len(result.get('customers', []))} customers")
        except Exception as e:
            print(f"✗ List customers failed: {e}")
            raise

    def test_update_customer(self):
        """Test updating customer"""
        
        if not created_customer_id:
            pytest.skip("No customer created")
        
        try:
            result = update_customer(
                created_customer_id,
                name=f"Updated Customer {TEST_CUSTOMER_ID}",
                city="New York"
            )
            print(f"✓ Customer updated: {result.get('customer', {}).get('name')}")
        except Exception as e:
            print(f"✗ Update customer failed: {e}")
            raise

    # ==============================================================================
    # BILLABLE METRIC TESTS
    # ==============================================================================

    def test_create_billable_metric(self):
        """Test billable metric creation"""
        global created_metric_code
        try:
            result = create_billable_metric(
                name=f"Test Metric {TEST_METRIC_CODE}",
                code=TEST_METRIC_CODE,
                aggregation_type="count_agg",
                description="Test metric for API calls"
            )
            created_metric_code = TEST_METRIC_CODE
            print(created_metric_code)
            print(f"✓ Billable metric created: {result.get('billable_metric', {}).get('code')}")
        except Exception as e:
            print(f"✗ Billable metric creation failed: {e}")
            raise

    def test_get_billable_metric(self):
        """Test getting billable metric"""
        if not created_metric_code:
            pytest.skip("No metric created")
        
        try:
            result = get_billable_metric(created_metric_code)
            print(f"✓ Billable metric retrieved: {result.get('billable_metric', {}).get('name')}")
        except Exception as e:
            print(f"✗ Get billable metric failed: {e}")
            raise

    def test_list_billable_metrics(self):
        """Test listing billable metrics"""
        try:
            result = list_billable_metrics(page=1, per_page=5)
            print(f"✓ Billable metrics listed: {len(result.get('billable_metrics', []))} metrics")
        except Exception as e:
            print(f"✗ List billable metrics failed: {e}")
            raise

    # ==============================================================================
    # PLAN TESTS
    # ==============================================================================

    def test_create_plan(self):
        """Test plan creation"""
        global created_plan_code
        if not created_metric_code:
            pytest.skip("No metric created for plan")
        
        try:
            print(created_metric_code)
            result = create_plan(
                name=f"Test Plan {TEST_PLAN_CODE}",
                code=TEST_PLAN_CODE,
                interval="monthly",
                amount_cents=2999,
                minimum_commitment={
                    "minimum_commitment": {
                    "amount_cents": 100000,
                    "invoice_display_name": "Minimum Commitment (C1)",
                    "tax_codes": [
                        "french_standard_vat"
                    ]
                    }},
                currency="USD",
                charges=[{
                    "billable_metric_id": created_metric_code,
                    "charge_model": "standard",
                    "properties": {"amount": "0.10"}
                }]
            )
            created_plan_code = TEST_PLAN_CODE
            
            print(f"✓ Plan created: {result.get('plan', {}).get('code')}")
        except Exception as e:
            print(f"✗ Plan creation failed: {e}")
            raise

    def test_get_plan(self):
        """Test getting plan"""
        if not created_plan_code:
            pytest.skip("No plan created")
        
        try:
            result = get_plan(created_plan_code)
            print(f"✓ Plan retrieved: {result.get('plan', {}).get('name')}")
        except Exception as e:
            print(f"✗ Get plan failed: {e}")
            raise

    def test_list_plans(self):
        """Test listing plans"""
        try:
            result = list_plans(page=1, per_page=5)
            
            print(f"✓ Plans listed: {len(result.get('plans', []))} plans")
        except Exception as e:
            print(f"✗ List plans failed: {e}")
            raise

    # ==============================================================================
    # SUBSCRIPTION TESTS
    # ==============================================================================

    def test_create_subscription(self):
        """Test subscription creation"""
        global created_subscription_id
        if not created_customer_id or not created_plan_code:
            pytest.skip("No customer or plan created")
        
        try:
            result = create_subscription(
                external_customer_id=created_customer_id,
                plan_code=created_plan_code,
                external_id=f"sub_{TEST_CUSTOMER_ID}"
            )
            created_subscription_id = f"sub_{TEST_CUSTOMER_ID}"
            print(f"✓ Subscription created: {result.get('subscription', {}).get('external_id')}")
        except Exception as e:
            print(f"✗ Subscription creation failed: {e}")
            raise

    def test_get_subscription(self):
        """Test getting subscription"""
        if not created_subscription_id:
            pytest.skip("No subscription created")
        
        try:
            result = get_subscription(created_subscription_id)
            print(f"✓ Subscription retrieved: {result.get('subscription', {}).get('status')}")
        except Exception as e:
            print(f"✗ Get subscription failed: {e}")
            raise

    def test_list_subscriptions(self):
        """Test listing subscriptions"""
        try:
            result = list_subscriptions(page=1, per_page=5)
            print(f"✓ Subscriptions listed: {len(result.get('subscriptions', []))} subscriptions")
        except Exception as e:
            print(f"✗ List subscriptions failed: {e}")
            raise

    # ==============================================================================
    # EVENT TESTS
    # ==============================================================================

    def test_record_usage(self):
        """Test recording usage event"""
        if not created_customer_id or not created_metric_code:
            pytest.skip("No customer or metric created")
        
        try:
            result = record_usage(
                external_customer_id=created_customer_id,
                code=created_metric_code,
                properties={"api_calls": 100},
                transaction_id=f"txn_{uuid.uuid4().hex[:8]}"
            )
            print(f"✓ Usage recorded: {result.get('event', {}).get('code')}")
        except Exception as e:
            print(f"✗ Record usage failed: {e}")
            raise

    # ==============================================================================
    # COUPON TESTS
    # ==============================================================================

    def test_create_coupon(self):
        """Test coupon creation"""
        global created_coupon_code
        try:
            result = create_coupon(
                name=f"Test Coupon {TEST_COUPON_CODE}",
                code=TEST_COUPON_CODE,
                coupon_type="fixed_amount",
                amount_cents=1000,
                currency="USD",
                frequency="once"
            )
            created_coupon_code = TEST_COUPON_CODE
            print(f"✓ Coupon created: {result.get('coupon', {}).get('code')}")
        except Exception as e:
            print(f"✗ Coupon creation failed: {e}")
            raise

    def test_get_coupon(self):
        """Test getting coupon"""
        if not created_coupon_code:
            pytest.skip("No coupon created")
        
        try:
            result = get_coupon(created_coupon_code)
            print(f"✓ Coupon retrieved: {result.get('coupon', {}).get('name')}")
        except Exception as e:
            print(f"✗ Get coupon failed: {e}")
            raise

    def test_apply_coupon(self):
        """Test applying coupon to customer"""
        if not created_customer_id or not created_coupon_code:
            pytest.skip("No customer or coupon created")
        
        try:
            result = apply_coupon(
                external_customer_id=created_customer_id,
                coupon_code=created_coupon_code
            )
            print(f"✓ Coupon applied: {result.get('applied_coupon', {}).get('id')}")
        except Exception as e:
            print(f"✗ Apply coupon failed: {e}")
            raise

    # ==============================================================================
    # ADD-ON TESTS
    # ==============================================================================

    def test_create_add_on(self):
        """Test add-on creation"""
        global created_add_on_code
        try:
            result = create_add_on(
                name=f"Test Add-on {TEST_ADD_ON_CODE}",
                code=TEST_ADD_ON_CODE,
                amount_cents=500,
                currency="USD",
                description="One-time setup fee"
            )
            created_add_on_code = TEST_ADD_ON_CODE
            print(f"✓ Add-on created: {result.get('add_on', {}).get('code')}")
        except Exception as e:
            print(f"✗ Add-on creation failed: {e}")
            raise

    def test_get_add_on(self):
        """Test getting add-on"""
        if not created_add_on_code:
            pytest.skip("No add-on created")
        
        try:
            result = get_add_on(created_add_on_code)
            print(f"✓ Add-on retrieved: {result.get('add_on', {}).get('name')}")
        except Exception as e:
            print(f"✗ Get add-on failed: {e}")
            raise

    def test_apply_add_on(self):
        """Test applying add-on to customer"""
        if not created_customer_id or not created_add_on_code:
            pytest.skip("No customer or add-on created")
        
        try:
            result = apply_add_on(
                external_customer_id=created_customer_id,
                add_on_code=created_add_on_code
            )
            print(f"✓ Add-on applied: {result.get('applied_add_on', {}).get('id')}")
        except Exception as e:
            print(f"✗ Apply add-on failed: {e}")
            raise

    # ==============================================================================
    # TAX TESTS
    # ==============================================================================

    def test_create_tax(self):
        """Test tax creation"""
        global created_tax_code
        try:
            result = create_tax(
                name=f"Test Tax {TEST_TAX_CODE}",
                code=TEST_TAX_CODE,
                rate=8.25,
                description="Sales tax"
            )
            created_tax_code = TEST_TAX_CODE
            print(f"✓ Tax created: {result.get('tax', {}).get('code')}")
        except Exception as e:
            print(f"✗ Tax creation failed: {e}")
            raise

    def test_get_tax(self):
        """Test getting tax"""
        if not created_tax_code:
            pytest.skip("No tax created")
        
        try:
            result = get_tax(created_tax_code)
            print(f"✓ Tax retrieved: {result.get('tax', {}).get('name')}")
        except Exception as e:
            print(f"✗ Get tax failed: {e}")
            raise

    def test_list_taxes(self):
        """Test listing taxes"""
        try:
            result = list_taxes(page=1, per_page=5)
            print(f"✓ Taxes listed: {len(result.get('taxes', []))} taxes")
        except Exception as e:
            print(f"✗ List taxes failed: {e}")
            raise

    # ==============================================================================
    # WALLET TESTS
    # ==============================================================================

    def test_create_wallet(self):
        """Test wallet creation"""
        global created_wallet_id
        if not created_customer_id:
            pytest.skip("No customer created")
        
        try:
            result = create_wallet(
                external_customer_id=created_customer_id,
                currency="USD",
                name="Test Wallet"
            )
            created_wallet_id = result.get('wallet', {}).get('lago_id')
            print(f"✓ Wallet created: {created_wallet_id}")
        except Exception as e:
            print(f"✗ Wallet creation failed: {e}")
            raise

    def test_get_wallet(self):
        """Test getting wallet"""
        if not created_wallet_id:
            pytest.skip("No wallet created")
        
        try:
            result = get_wallet(created_wallet_id)
            print(f"✓ Wallet retrieved: {result.get('wallet', {}).get('name')}")
        except Exception as e:
            print(f"✗ Get wallet failed: {e}")
            raise

    def test_list_wallets(self):
        """Test listing wallets"""
        if not created_customer_id:
            pytest.skip("No customer created")
        
        try:
            result = list_wallets(external_customer_id=created_customer_id)
            print(f"✓ Wallets listed: {len(result.get('wallets', []))} wallets")
        except Exception as e:
            print(f"✗ List wallets failed: {e}")
            raise

    def test_create_wallet_transaction(self):
        """Test wallet transaction creation"""
        if not created_wallet_id:
            pytest.skip("No wallet created")
        
        try:
            result = create_wallet_transaction(
                wallet_id=created_wallet_id,
                amount="10.00",
                transaction_type="inbound"
            )
            print(f"✓ Wallet transaction created: {result.get('wallet_transaction', {}).get('amount')}")
        except Exception as e:
            print(f"✗ Wallet transaction creation failed: {e}")
            raise

    # ==============================================================================
    # INVOICE TESTS
    # ==============================================================================

    def test_list_invoices(self):
        """Test listing invoices"""
        try:
            result = list_invoices(page=1, per_page=5)
            global created_invoice_id
            invoices = result.get('invoices', [])
            if invoices:
                created_invoice_id = invoices[0].get('lago_id')
            print(f"✓ Invoices listed: {len(invoices)} invoices")
        except Exception as e:
            print(f"✗ List invoices failed: {e}")
            raise

    def test_get_invoice(self):
        """Test getting invoice"""
        if not created_invoice_id:
            pytest.skip("No invoice available")
        
        try:
            result = get_invoice(created_invoice_id)
            print(f"✓ Invoice retrieved: {result.get('invoice', {}).get('number')}")
        except Exception as e:
            print(f"✗ Get invoice failed: {e}")
            raise

    # ==============================================================================
    # ANALYTICS TESTS
    # ==============================================================================

    def test_get_gross_revenue(self):
        """Test getting gross revenue analytics"""
        try:
            result = get_gross_revenue(currency="USD")
            print(f"✓ Gross revenue analytics: {result.get('gross_revenue', {})}")
        except Exception as e:
            print(f"✗ Get gross revenue failed: {e}")
            raise

    def test_get_mrr(self):
        """Test getting MRR analytics"""
        try:
            result = get_mrr(currency="USD")
            print(f"✓ MRR analytics: {result.get('mrr', {})}")
        except Exception as e:
            print(f"✗ Get MRR failed: {e}")
            raise

    # ==============================================================================
    # ORGANIZATION TESTS
    # ==============================================================================

    def test_get_organization(self):
        """Test getting current organization"""
        try:
            result = get_organization()
            print(f"✓ Organization retrieved: {result.get('organization', {}).get('name')}")
        except Exception as e:
            print(f"✗ Get organization failed: {e}")
            raise

    # ==============================================================================
    # CLEANUP TESTS (Run last)
    # ==============================================================================

    def test_zzz_cleanup_subscription(self):
        """Test terminating subscription (cleanup)"""
        if not created_subscription_id:
            pytest.skip("No subscription to cleanup")
        
        try:
            result = terminate_subscription(created_subscription_id)
            print(f"✓ Subscription terminated: {result.get('subscription', {}).get('status')}")
        except Exception as e:
            print(f"✗ Subscription termination failed: {e}")

    def test_zzz_cleanup_wallet(self):
        """Test terminating wallet (cleanup)"""
        if not created_wallet_id:
            pytest.skip("No wallet to cleanup")
        
        try:
            result = terminate_wallet(created_wallet_id)
            print(f"✓ Wallet terminated")
        except Exception as e:
            print(f"✗ Wallet termination failed: {e}")

    def test_zzz_cleanup_customer(self):
        """Test deleting customer (cleanup)"""
        if not created_customer_id:
            pytest.skip("No customer to cleanup")
        
        try:
            result = delete_customer(created_customer_id)
            print(f"✓ Customer deleted")
        except Exception as e:
            print(f"✗ Customer deletion failed: {e}")

    def test_zzz_cleanup_plan(self):
        """Test deleting plan (cleanup)"""
        if not created_plan_code:
            pytest.skip("No plan to cleanup")
        
        try:
            result = delete_plan(created_plan_code)
            print(f"✓ Plan deleted")
        except Exception as e:
            print(f"✗ Plan deletion failed: {e}")

    def test_zzz_cleanup_billable_metric(self):
        """Test deleting billable metric (cleanup)"""
        if not created_metric_code:
            pytest.skip("No metric to cleanup")
        
        try:
            result = delete_billable_metric(created_metric_code)
            print(f"✓ Billable metric deleted")
        except Exception as e:
            print(f"✗ Billable metric deletion failed: {e}")

    def test_zzz_cleanup_coupon(self):
        """Test deleting coupon (cleanup)"""
        if not created_coupon_code:
            pytest.skip("No coupon to cleanup")
        
        try:
            result = delete_coupon(created_coupon_code)
            print(f"✓ Coupon deleted")
        except Exception as e:
            print(f"✗ Coupon deletion failed: {e}")

    def test_zzz_cleanup_add_on(self):
        """Test deleting add-on (cleanup)"""
        if not created_add_on_code:
            pytest.skip("No add-on to cleanup")
        
        try:
            result = delete_add_on(created_add_on_code)
            print(f"✓ Add-on deleted")
        except Exception as e:
            print(f"✗ Add-on deletion failed: {e}")

    def test_zzz_cleanup_tax(self):
        """Test deleting tax (cleanup)"""
        if not created_tax_code:
            pytest.skip("No tax to cleanup")
        
        try:
            result = delete_tax(created_tax_code)
            print(f"✓ Tax deleted")
        except Exception as e:
            print(f"✗ Tax deletion failed: {e}")


# ==============================================================================
# INTEGRATION TEST RUNNER
# ==============================================================================

def run_integration_tests():
    """Run integration tests with proper order"""
    print("🚀 Starting Lago API Integration Tests")
    print("=" * 50)
    
    test_class = TestLagoService()
    test_class.setup()
    
    # Test order matters due to dependencies
    test_methods = [
        # Basic health check
        "test_health_check",
        
        # Create resources
        "test_create_customer",
        "test_create_billable_metric", 
        "test_create_plan",
        "test_create_coupon",
        "test_create_add_on",
        "test_create_tax",
        
        # Create dependent resources
        "test_create_subscription",
        "test_create_wallet",
        
        # Test retrieval
        "test_get_customer",
        "test_get_billable_metric",
        "test_get_plan",
        "test_get_coupon",
        "test_get_add_on",
        "test_get_tax",
        "test_get_subscription",
        "test_get_wallet",
        
        # Test updates
        "test_update_customer",
        
        # Test listings
        "test_list_customers",
        "test_list_billable_metrics",
        "test_list_plans",
        "test_list_subscriptions",
        "test_list_taxes",
        "test_list_wallets",
        "test_list_invoices",
        
        # Test actions
        "test_record_usage",
        "test_apply_coupon",
        "test_apply_add_on",
        "test_create_wallet_transaction",
        
        # Test invoice operations
        "test_get_invoice",
        
        # Test analytics
        "test_get_gross_revenue",
        "test_get_mrr",
        
        # Test organization
        "test_get_organization",
        
        # Cleanup (order matters)
        "test_zzz_cleanup_subscription",
        "test_zzz_cleanup_wallet",
        "test_zzz_cleanup_customer",
        "test_zzz_cleanup_plan",
        "test_zzz_cleanup_billable_metric",
        "test_zzz_cleanup_coupon",
        "test_zzz_cleanup_add_on",
        "test_zzz_cleanup_tax",
    ]
    
    passed = 0
    failed = 0
    skipped = 0
    
    for method_name in test_methods:
        try:
            print(f"\n🧪 Running {method_name}...")
            method = getattr(test_class, method_name)
            method()
            passed += 1
        except pytest.skip.Exception as e:
            print(f"⚠️  Skipped: {e}")
            skipped += 1
        except Exception as e:
            print(f"❌ Failed: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"⚠️  Skipped: {skipped}")
    print(f"📈 Total: {passed + failed + skipped}")
    
    if failed == 0:
        print("🎉 All tests passed!")
    else:
        print("⚠️  Some tests failed. Check the logs above.")


# ==============================================================================
# MOCK TESTS (for when Lago API is not available)
# ==============================================================================

class TestLagoServiceMocked:
    """Mocked tests for when API is not available"""

    @patch('requests.post')
    @patch('requests.get')
    def test_create_customer_mocked(self, mock_get, mock_post):
        """Test customer creation with mocked API"""
        mock_post.return_value.json.return_value = {
            "customer": {
                "external_id": "test_customer",
                "email": "test@example.com",
                "name": "Test Customer"
            }
        }
        mock_post.return_value.raise_for_status.return_value = None
        
        result = create_customer("test_customer", "test@example.com", "Test Customer")
        assert result["customer"]["external_id"] == "test_customer"
        print("✓ Mocked customer creation test passed")

    @patch('requests.post')
    def test_record_usage_mocked(self, mock_post):
        """Test usage recording with mocked API"""
        mock_post.return_value.json.return_value = {
            "event": {
                "code": "api_calls",
                "external_customer_id": "test_customer"
            }
        }
        mock_post.return_value.raise_for_status.return_value = None
        
        result = record_usage("test_customer", "api_calls", {"count": 100})
        assert result["event"]["code"] == "api_calls"
        print("✓ Mocked usage recording test passed")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run Lago API tests")
    parser.add_argument("--mock", action="store_true", help="Run mocked tests")
    parser.add_argument("--integration", action="store_true", help="Run integration tests")
    args = parser.parse_args()
    
    if args.mock:
        print("Running mocked tests...")
        mock_test = TestLagoServiceMocked()
        mock_test.test_create_customer_mocked()
        mock_test.test_record_usage_mocked()
        print("Mocked tests completed!")
    elif args.integration:
        run_integration_tests()
    else:
        print("Usage:")
        print("  python test_lago_service.py --integration  # Run integration tests")
        print("  python test_lago_service.py --mock        # Run mocked tests")
        print("  pytest test_lago_service.py               # Run with pytest")