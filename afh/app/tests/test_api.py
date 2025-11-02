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
        "Body": "start",
        "MessageSid": "SM1234567890",
        "AccountSid": "AC1234567890"
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


def test_get_session(session_id):
    """Test get session endpoint"""
    print(f"\n🔍 Testing Get Session: {session_id}...")
    
    response = requests.get(f"{BASE_URL}/api/session/{session_id}")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    return response.status_code == 200


def test_chat_interface(session_id):
    """Test chat interface HTML"""
    print(f"\n💬 Testing Chat Interface: {session_id}...")
    
    response = requests.get(f"{BASE_URL}/chat/{session_id}")
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        print(f"✅ Chat interface loaded successfully")
        print(f"🌐 Open in browser: {BASE_URL}/chat/{session_id}")
        return True
    else:
        print(f"❌ Failed to load chat interface")
        return False


def test_websocket_simulation(session_id):
    """Simulate WebSocket messages (requires websocket-client)"""
    try:
        from websocket import create_connection
        
        print(f"\n🔌 Testing WebSocket: {session_id}...")
        
        ws_url = f"ws://localhost:8000/ws/{session_id}"
        ws = create_connection(ws_url)
        
        # Receive initial message
        result = ws.recv()
        print(f"Received: {result[:200]}...")
        
        # Send a message
        message = {
            "type": "user_message",
            "message": "1"
        }
        ws.send(json.dumps(message))
        print(f"Sent: {message}")
        
        # Receive response
        result = ws.recv()
        print(f"Received: {result[:200]}...")
        
        ws.close()
        print("✅ WebSocket test completed")
        return True
        
    except ImportError:
        print("⚠️  websocket-client not installed. Run: pip install websocket-client")
        return False
    except Exception as e:
        print(f"❌ WebSocket test failed: {e}")
        return False


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("AFHSync Chatbot API Test Suite")
    print("=" * 60)
    
    results = {}
    
    # Test 1: Health Check
    results['health'] = test_health()
    time.sleep(1)
    
    # Test 2: SMS Webhook
    session_id = test_sms_webhook()
    results['sms'] = session_id is not None
    time.sleep(1)
    
    if session_id:
        # Test 3: Get Session
        results['get_session'] = test_get_session(session_id)
        time.sleep(1)
        
        # Test 4: Chat Interface
        results['chat_interface'] = test_chat_interface(session_id)
        time.sleep(1)
        
        # Test 5: WebSocket (optional)
        results['websocket'] = test_websocket_simulation(session_id)
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name.ljust(20)}: {status}")
    
    total = len(results)
    passed = sum(results.values())
    print(f"\nTotal: {passed}/{total} tests passed")
    print("=" * 60)
    
    if session_id:
        print(f"\n🌐 Open chat in browser:")
        print(f"   {BASE_URL}/chat/{session_id}")
        print(f"\n📚 API Documentation:")
        print(f"   {BASE_URL}/docs")


if __name__ == "__main__":
    try:
        run_all_tests()
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test suite error: {e}")