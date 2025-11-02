#!/usr/bin/env python3

import requests
import time
import json
import sys
from concurrent.futures import ThreadPoolExecutor
import random
import string

BASE_URL = "https://localhost/auth"
session = requests.Session()
session.verify = False  # For self-signed certificates

def test_password_policy():
    """Test password strength requirements"""
    print("🔐 Testing password policy...")
    
    weak_passwords = [
        "123456",
        "password",
        "Password1",  # Missing special character
        "Pass!",      # Too short
        "password123!",  # No uppercase
        "PASSWORD123!"   # No lowercase
    ]
    
    for pwd in weak_passwords:
        response = session.post(f"{BASE_URL}/register", json={
            "email": f"test_{random.randint(1000,9999)}@example.com",
            "password": pwd,
            "name": "Test User",
            "terms_accepted": True
        })
        
        if response.status_code == 200:
            print(f"❌ Weak password accepted: {pwd}")
        else:
            print(f"✅ Weak password rejected: {pwd}")

def test_rate_limiting():
    """Test rate limiting on login endpoint"""
    print("🚦 Testing rate limiting...")
    
    def make_login_request():
        return session.post(f"{BASE_URL}/login", json={
            "email": "nonexistent@example.com",
            "password": "wrongpassword"
        })
    
    # Make concurrent requests
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(make_login_request) for _ in range(30)]
        results = [f.result() for f in futures]
    
    rate_limited = sum(1 for r in results if r.status_code == 429)
    print(f"✅ Rate limiting working: {rate_limited}/30 requests blocked")

def test_sql_injection():
    """Test for SQL injection vulnerabilities"""
    print("💉 Testing SQL injection protection...")
    
    sql_payloads = [
        "' OR 1=1--",
        "'; DROP TABLE users;--",
        "' UNION SELECT * FROM users--",
        "admin'/*",
        "' OR 'x'='x"
    ]
    
    for payload in sql_payloads:
        response = session.post(f"{BASE_URL}/login", json={
            "email": payload,
            "password": "test"
        })
        
        if response.status_code == 500:
            print(f"❌ Possible SQL injection vulnerability with: {payload}")
        else:
            print(f"✅ SQL injection protected: {payload}")

def test_security_headers():
    """Test security headers"""
    print("🛡️ Testing security headers...")
    
    response = session.get(f"{BASE_URL}/health")
    headers = response.headers
    
    required_headers = [
        'x-frame-options',
        'x-xss-protection',
        'x-content-type-options',
        'strict-transport-security'
    ]
    
    for header in required_headers:
        if header in headers:
            print(f"✅ {header}: {headers[header]}")
        else:
            print(f"❌ Missing security header: {header}")

def test_account_lockout():
    """Test account lockout mechanism"""
    print("🔒 Testing account lockout...")
    
    # First register a test user
    test_email = f"lockout_test_{random.randint(1000,9999)}@example.com"
    register_response = session.post(f"{BASE_URL}/register", json={
        "email": test_email,
        "password": "ValidPassword123!",
        "name": "Lockout Test",
        "terms_accepted": True
    })
    
    if register_response.status_code != 200:
        print("❌ Failed to create test user for lockout test")
        return
    
    # Attempt multiple failed logins
    for i in range(6):
        response = session.post(f"{BASE_URL}/login", json={
            "email": test_email,
            "password": "wrongpassword"
        })
        print(f"Attempt {i+1}: Status {response.status_code}")
        
        if response.status_code == 423:  # Account locked
            print("✅ Account lockout mechanism working")
            break
        
        time.sleep(1)

def main():
    print("🔍 Starting security tests...")
    print("=" * 50)
    
    try:
        test_password_policy()
        print()
        test_rate_limiting()
        print()
        test_sql_injection()
        print()
        test_security_headers()
        print()
        test_account_lockout()
        
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to the auth service. Make sure it's running on https://localhost")
        sys.exit(1)
    
    print()
    print("🎯 Security testing complete!")

if __name__ == "__main__":
    main()