"""
Test script for AFHSync Chatbot API
Run this to test the SMS webhook and chat functionality
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"


def test_health():
    """Test health endpoint"""
    print("\n🏥 Testing Health Endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200


def test_sms_webhook(phone="+12065551236"):
    """Test SMS webhook"""
    print(f"\n📱 Testing SMS Webhook for {phone}...")
    
    data = {
        "From": phone,
        "Body": "hello waht service do you offer",
        "MessageSid": f"SM1234567891-{phone}",
        "AccountSid": f"AC1234567891-{phone}"
    }
    
    response = requests.post(f"{BASE_URL}/webhook/sms", data=data)
    print(f"Status: {response.status_code}")
    print(f"Response:\n{response.text[:500]}")
    
    # Extract session ID from response
    if "localhost:8000/chat/" in response.text:
        session_id = response.text.split("/chat/")[1].split('"')[0].split("\n")[0].strip()
        print(f"\n✅ Session Created: {session_id}")
        return session_id.replace("</Message>","")
    
    return None

def test_sms_response(phone="+12065551236",msg=None):
    """Test SMS webhook"""
    print(f"\n📱 Testing SMS Webhook for {phone}...")
    
    data = {
        "From": phone,
        "Body": msg,
        "MessageSid": f"SM1234567801-{phone}",
        "AccountSid": f"AC1234560891-{phone}"
    }
    
    response = requests.post(f"{BASE_URL}/webhook/sms", data=data)
    print(f"Status: {response.status_code}")
    print(f"Response:\n{response.text[:500]}")
    
    # Extract session ID from response
    if "localhost:8000/chat/" in response.text:
        session_id = response.text.split("/chat/")[1].split('"')[0].split("\n")[0].strip()
        print(f"\n✅ Session Created: {session_id}")
        return session_id.replace("</Message>","")
    
    return None




if __name__ == "__main__":
    try:
        x = test_sms_response(phone="+12065551239",msg="weekdays")
        print(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test suite error: {e}")