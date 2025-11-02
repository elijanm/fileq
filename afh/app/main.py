"""
AFHSync FastAPI Application
Clean implementation with Jinja2 templates and AI-powered intelligence
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException,UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from intents.sms import SMSIntentAnalyzer
from utils.monitor import ResourceMonitor
from typing import Optional, Dict
import redis,asyncio
import json
import time
import logging
import uuid
import threading
from datetime import datetime
import os
from dotenv import load_dotenv
from services.chatbot import AFHSyncBot
from utils.util import MongoDBHandler
from handlers.intelligent_handler import IntelligentMessageHandler
import psutil
from handlers.sms_manager import SMSConversationManager,SMSConversationState
# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
redis_client=None

DB_FILE = "monitor.duckdb"


process = psutil.Process(os.getpid())

def my_alert(severity, rss, cpu, baseline, deviation):
    print(f"ALERT! {severity}: Memory at {rss:.1f}MB")
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("AFHSync Started")
    # Redis
    try:
        redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            password=os.getenv("REDIS_PASSWORD", None),
            db=0,
            decode_responses=True
        )
        SessionManager.initialize(redis_client)
        logger.info("Redis connected")
        
        if os.environ.get("RUN_MAIN") != "true":
          monitor = ResourceMonitor(alert_callback=my_alert)
          monitor.start()
    except Exception as e:
        logger.warning(f"Redis unavailable: {e}")
        redis_client = None
        if os.environ.get("RUN_MAIN") != "true":
           monitor.stop()
    
    yield   # <- app runs here
    
    # Shutdown logic
    for ws in active_connections.values():
        await ws.close()
    active_connections.clear()
    intelligent_handlers.clear()
    logger.info("AFHSync Stopped")
   
    
    
# FastAPI
app = FastAPI(title="AFHSync Chatbot", version="1.0.0",lifespan=lifespan)

# Jinja2 Templates
templates = Jinja2Templates(directory="templates")

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# Fallback storage
memory_sessions: Dict[str, dict] = {}

# MongoDB
db = MongoDBHandler()

# Active connections
active_connections: Dict[str, WebSocket] = {}
intelligent_handlers: Dict[str, IntelligentMessageHandler] = {}





# In main.py - Update SessionManager class
SESSION_EXPIRY = int(os.getenv('SESSION_EXPIRY', 3600*24*365*5))

class SessionManager:
    """Session management with ObjectId handling"""
    redis_client = None  # Will be set during initialization
    
    @classmethod
    def initialize(cls, redis_client):
        """Initialize with Redis client"""
        cls.redis_client = redis_client
        try:
            cls.redis_client.ping()
            logger.info("SessionManager initialized with Redis")
            cls.cleanup_expired_sessions()
        except Exception as e:
            logger.error(f"Redis initialization failed: {e}")
            raise
    
    @staticmethod
    def _serialize_data(data: dict) -> dict:
        """Remove or convert non-serializable objects"""
        serialized = {}
        for key, value in data.items():
            if key == '_id':
                # Convert ObjectId to string
                serialized[key] = str(value)
            elif isinstance(value, datetime):
                # Convert datetime to ISO string
                serialized[key] = value.isoformat()
            elif isinstance(value, list):
                # Handle lists that might contain ObjectIds
                serialized[key] = [
                    str(item) if hasattr(item, "__class__") and item.__class__.__name__ == "ObjectId"
                    else item.isoformat() if isinstance(item, datetime)
                    else item
                    for item in value
                ]
                
            elif isinstance(value, dict):
                # Recursively serialize nested dicts
                serialized[key] = SessionManager._serialize_data(value)
            elif hasattr(value, '__class__') and value.__class__.__name__ == 'ObjectId':
                # Handle any ObjectId
                serialized[key] = str(value)
            else:
                serialized[key] = value
        return serialized
    
    @classmethod
    def create_session(cls, session_id: str, bot_state: str, bot_data: dict) -> bool:
        """Create session with TTL"""
        try:
            session_data = {
                'session_id': session_id,
                'bot_state': bot_state,
                'bot_data': bot_data,
                'created_at': datetime.utcnow().isoformat(),
                'last_activity': datetime.utcnow().isoformat()
            }
            
            key = f"session:{session_id}"
            
            # Set with TTL - CRITICAL
            cls.redis_client.setex(
                key,
                SESSION_EXPIRY,
                json.dumps(session_data)
            )
            
            logger.info(f"Session created: {session_id} (expires in {SESSION_EXPIRY}s)")
            return True
            
        except Exception as e:
            logger.error(f"Session creation error: {e}")
            return False
    
    @classmethod
    def get_session(cls, session_id: str) -> dict:
        """Get session and refresh TTL"""
        try:
            key = f"session:{session_id}"
            data = cls.redis_client.get(key)
            
            if data:
                # Refresh TTL on access - CRITICAL
                cls.redis_client.expire(key, SESSION_EXPIRY)
                
                session = json.loads(data)
                logger.debug(f"Session retrieved: {session_id}")
                return session
            
            logger.warning(f"Session not found: {session_id}")
            return None
            
        except Exception as e:
            logger.error(f"Session retrieval error: {e}")
            return None
    
    @classmethod
    def update_session(cls, session_id: str, bot_state: str, bot_data: dict) -> bool:
        """Update session and refresh TTL"""
        try:
            key = f"session:{session_id}"
            
            # Get existing or create new
            existing = cls.get_session(session_id)
            serialized_data = cls._serialize_data(bot_data)
            session_data = {
                'session_id': session_id,
                'bot_state': bot_state,
                'bot_data': serialized_data,
                'created_at': existing.get('created_at') if existing else datetime.utcnow().isoformat(),
                'last_activity': datetime.utcnow().isoformat()
            }
            
            # Update with refreshed TTL - CRITICAL
            cls.redis_client.setex(
                key,
                SESSION_EXPIRY,
                json.dumps(session_data)
            )
            
            logger.debug(f"Session updated: {session_id} (TTL reset to {SESSION_EXPIRY}s)")
            return True
            
        except Exception as e:
            logger.error(f"Session update error: {e}")
            return False
    
    @classmethod
    def delete_session(cls, session_id: str) -> bool:
        """Delete session immediately"""
        try:
            key = f"session:{session_id}"
            cls.redis_client.delete(key)
            logger.info(f"Session deleted: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Session deletion error: {e}")
            return False
    
    @classmethod
    def get_session_ttl(cls, session_id: str) -> int:
        """Check remaining TTL for debugging"""
        try:
            key = f"session:{session_id}"
            ttl = cls.redis_client.ttl(key)
            logger.debug(f"Session {session_id} TTL: {ttl}s")
            return ttl
        except Exception as e:
            logger.error(f"TTL check error: {e}")
            return -1
    
    @classmethod
    def cleanup_expired_sessions(cls):
        """Manual cleanup (Redis should do this automatically with TTL)"""
        try:
            # Scan for expired sessions
            cursor = 0
            cleaned = 0
            
            while True:
                cursor, keys = cls.redis_client.scan(cursor, match="session:*", count=100)
                
                for key in keys:
                    ttl = cls.redis_client.ttl(key)
                    if ttl == -1:  # No expiry set
                        cls.redis_client.expire(key, SESSION_EXPIRY)
                        cleaned += 1
                
                if cursor == 0:
                    break
            
            if cleaned > 0:
                logger.info(f"Cleaned up {cleaned} sessions without TTL")
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
    
    @classmethod
    def get_session_by_phone(cls, phone: str) -> Optional[dict]:
        """Get session by phone number with TTL refresh"""
        try:
            # Scan for session with this phone
            cursor = 0
            while True:
                cursor, keys = cls.redis_client.scan(cursor, match="session:*", count=100)
                
                for key in keys:
                    data = cls.redis_client.get(key)
                    if data:
                        session = json.loads(data)
                        bot_data = session.get('bot_data', {})
                        
                        if bot_data.get('contact') == phone:
                            # Found it - refresh TTL
                            cls.redis_client.expire(key, SESSION_EXPIRY)
                            logger.debug(f"Session found for {phone}, TTL refreshed")
                            return session
                
                if cursor == 0:
                    break
            
            logger.debug(f"No session found for {phone}")
            return None
            
        except Exception as e:
            logger.error(f"Session lookup error: {e}")
            return None

    @classmethod
    def create_session_with_phone(cls, phone: str, bot_state: str, bot_data: dict) -> str:
        """Create session with phone identifier"""
        session_id = f"sms_{phone}_{int(datetime.utcnow().timestamp())}"
        
        bot_data['contact'] = phone
        bot_data['channel'] = 'sms'
        
        cls.create_session(session_id, bot_state, bot_data)
        
        return session_id
        
    

@app.post("/upload/{session_id}")
async def upload_file(session_id: str, file: UploadFile):
    """Handle file uploads in browser portal"""
    session = SessionManager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    
    # Save file
    file_path = f"uploads/{session['contact']}/{file.filename}"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    with open(file_path, "wb") as f:
        f.write(await file.read())
    
    # Update user record
    db.add_to_array(session['contact'], 'uploaded_files', {
        'filename': file.filename,
        'path': file_path,
        'uploaded_at': datetime.utcnow()
    })
    
    return {"success": True, "filename": file.filename}
# SMS Webhook
@app.post("/webhook/sms")
@app.post("/sms")
async def sms_webhook(request: Request):
    """Enhanced SMS webhook with proper session TTL and intent detection"""
    try:
        form = await request.form()
        phone = form.get('From', '').strip().replace('+', '').replace('-', '').replace(' ', '')
        message = form.get('Body', '').strip()
        
        logger.info(f"SMS from {phone}: {message}")
        
        if not phone:
            raise HTTPException(400, "Phone required")
        
        # Get or create session with TTL
        session_data = SessionManager.get_session_by_phone(phone)
        user_data = db.find_user_by_contact(phone)
        
        if not session_data:
            # Create new session
            session_id = f"sms_{phone}_{int(datetime.utcnow().timestamp())}"
            bot = AFHSyncBot()
            
            # Create user if doesn't exist
            if not user_data:
                db.create_user({
                    'contact': phone,
                    'contact_type': 'phone',
                    'created_at': datetime.utcnow(),
                    'status': 'new',
                    'profile_complete': False,
                    'first_message': message,
                    'channel': 'sms'
                })
                user_data = {'contact': phone, 'status': 'new'}
            
            # Create session with bot data
            bot.data['contact'] = phone
            bot.data['channel'] = 'sms'
            SessionManager.create_session(session_id, bot.state.value, bot.data)
            logger.info(f"New SMS session: {session_id}")
        else:
            # Restore existing session and refresh TTL
            
            session_id = session_data['session_id']
            logger.info(f"NRestore SMS session: {session_id}")
            bot = AFHSyncBot()
            
            try:
                bot.state = bot.state.__class__[session_data['bot_state'].upper()]
            except KeyError:
                bot.state = bot.state.__class__['START']
            
            # bot.data = session_data.get('bot_data', {})
            
            if user_data:
                bot.data.update(user_data)
                bot.data.pop('_id', None)
            else:
                bot.data.update(session_data.get('bot_data', {}))
            
            # Refresh TTL on activity
            SessionManager.update_session(session_id, bot.state.value, bot.data)
            
            ttl = SessionManager.get_session_ttl(session_id)
            logger.info(f"SMS session restored: {session_id}, TTL: {ttl}s")
        
        # Analyze intent
        intent = SMSIntentAnalyzer.analyze_intent(message, user_data)
        logger.info(f"Intent: {intent['intent_type']} | Channel: {intent['best_channel']} | Confidence: {intent['confidence']}")
        
        # Update user with intent tracking
        if user_data:
            db.update_user(phone, {
                'last_intent': intent['intent_type'],
                'last_intent_confidence': intent['confidence'],
                'last_contact': datetime.utcnow(),
                'last_message': message
            })
        
        # Process conversation
        conversation_manager = SMSConversationManager(db)
        state_manager = SMSConversationState(db)
        state = state_manager.get_state(phone)
        
        response_text = await conversation_manager.handle_sms_conversation(
            phone, message, session_id, state, intent, user_data
        )
        
        # Update session after processing - CRITICAL for TTL refresh
        SessionManager.update_session(session_id, bot.state.value, bot.data)
        
        # Log TTL after update
        ttl = SessionManager.get_session_ttl(session_id)
        logger.info(f"Response sent, session TTL: {ttl}s")
        logger.info(f"Response: {response_text[:100]}...")
        
        return HTMLResponse(
            content=f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{response_text}</Message>
</Response>""",
            media_type="application/xml"
        )
        
    except Exception as e:
        logger.error(f"SMS error: {e}", exc_info=True)
        
        return HTMLResponse(
            content=f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>Welcome to AFHSync! We're experiencing technical difficulties. Please try again shortly.</Message>
</Response>""",
            media_type="application/xml"
        )
# Chat Interface - JINJA2
@app.get("/chat/{session_id}", response_class=HTMLResponse)
async def chat_interface(request: Request, session_id: str, theme: str = "green"):
    """Chat interface with Jinja2"""
    session = SessionManager.get_session(session_id)
    
    if not session:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error_title": "Session Expired",
                "error_message": "Your session has expired or is invalid.",
                "error_hint": "Please text us again to start a new conversation."
            }
        )
    
    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "session_id": session_id,
            "theme": theme,
            "created_at": session.get('created_at'),
            "phone": session.get('phone', 'User')
        }
    )


# WebSocket
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket with context-aware greeting and proper session TTL"""
    start = time.time()
    await websocket.accept()
    active_connections[session_id] = websocket
    logger.info(f"websocket.accept: {(time.time()-start)*1000:.0f}ms")
    
    try:
        # Check session TTL
        t1=time.time()
        ttl = SessionManager.get_session_ttl(session_id)
        logger.info(f"SessionManager.get_session_ttl: {(time.time()-t1)*1000:.0f}ms")
        logger.info(f"WebSocket connected: {session_id}, TTL: {ttl}s")
        
        # Get or create session
        t2=time.time()
        session_data = SessionManager.get_session(session_id)
        logger.info(f"SessionManager.get_session_ttl: {(time.time()-t2)*1000:.0f}ms")
        # Small delay to ensure connection is fully established
        await asyncio.sleep(0.1)
        
        if not session_data:
            # New session - create fresh
            bot = AFHSyncBot()
            t3=time.time()
            SessionManager.create_session(session_id, bot.state.value, bot.data)
            logger.info(f"New session created: {session_id}")
            logger.info(f"SessionManager.create_session: {(time.time()-t3)*1000:.0f}ms")
            
            # Get phone from query params or wait for user input
            phone = None
            user_data = None
        else:
            # Existing session - restore state
            phone = session_data.get('bot_data', {}).get('contact')
            t4=time.time()
            user_data = db.find_user_by_contact(phone) if phone else None
            logger.info(f"SessionManager.get_session_ttl: {(time.time()-t4)*1000:.0f}ms")
            
            # Initialize bot with saved state
            bot = AFHSyncBot()
            try:
                bot.state = bot.state.__class__[session_data['bot_state'].upper()]
            except KeyError:
                bot.state = bot.state.__class__['START']
            
            # Merge user data
            if user_data:
                bot.data.update(user_data)
                bot.data.pop('_id', None)  # Remove MongoDB ID
            else:
                bot.data.update(session_data.get('bot_data', {}))
            
            logger.info(f"Session restored: {session_id}, State: {bot.state.value}, User: {phone}")
        
        # Initialize intelligent handler
        if session_id not in intelligent_handlers:
            intelligent_handlers[session_id] = IntelligentMessageHandler(bot)
        handler = intelligent_handlers[session_id]
        
        # Send context-aware welcome
        t5=time.time()
        welcome_msg = generate_context_welcome(user_data, bot.data)
        logger.info(f"generate_context_welcome: {(time.time()-t5)*1000:.0f}ms")
        t6=time.time()
        await websocket.send_json({'type': 'bot_response', 'message': welcome_msg})
        logger.info(f"websocket.send_json: {(time.time()-t6)*1000:.0f}ms")
        
        # Update session with TTL refresh
        SessionManager.update_session(session_id, bot.state.value, bot.data)
        
        # Message loop
        while True:
            data = await websocket.receive_json()
            
            if data['type'] == 'user_message':
                # Process message
                response = handler.process_with_intelligence(
                    data['message'],
                    bot.state.value,
                    bot.data.get('role'),
                    session_id
                )
                
                # Update session with refreshed TTL - CRITICAL
                SessionManager.update_session(session_id, bot.state.value, bot.data)
                
                # Log TTL for debugging
                ttl = SessionManager.get_session_ttl(session_id)
                logger.debug(f"Message processed, session {session_id} TTL: {ttl}s")
                
                await websocket.send_json({'type': 'bot_response', 'message': response})
            
            elif data['type'] == 'ping':
                # Heartbeat to keep session alive
                SessionManager.update_session(session_id, bot.state.value, bot.data)
                await websocket.send_json({'type': 'pong'})
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
        # Cleanup
        if session_id in active_connections:
            del active_connections[session_id]
        if session_id in intelligent_handlers:
            del intelligent_handlers[session_id]
        # Don't delete session - let TTL expire naturally
    
    except Exception as e:
        logger.error(f"WebSocket error for {session_id}: {e}", exc_info=True)
        try:
            await websocket.send_json({'type': 'error', 'message': 'An error occurred'})
        except:
            pass
        await websocket.close()
    finally:
        logger.info(f"websocket.finally: {(time.time()-start)*1000:.0f}ms")
        
@app.websocket("/ws/{session_id}")
async def websocket_endpoint_old2(websocket: WebSocket, session_id: str):
    """WebSocket with context-aware greeting"""
    await websocket.accept()
    active_connections[session_id] = websocket
    
    try:
        ttl = SessionManager.get_session_ttl(session_id)
        logger.info(f"WebSocket connected: {session_id}, TTL: {ttl}s")
        
        
        session_data = SessionManager.get_session(session_id)
        if not session_data:
            # Create new session
            bot = AFHSyncBot()
            SessionManager.create_session(session_id, bot.state.value, bot.data)
            logger.info(f"New session created: {session_id}")
        else:
            # Load existing session
            bot = AFHSyncBot()
            bot.state = bot.state.__class__[session_data['bot_state'].upper()]
            bot.data = session_data.get('bot_data', {})
            logger.info(f"Session restored: {session_id}")
        
        handler = IntelligentMessageHandler(bot)
        # if not session:
        #     await websocket.send_json({'type': 'error', 'message': 'Session not found'})
        #     await websocket.close()
        #     SessionManager.create_session(session_id, bot.state.value, bot.data)
        #     return
        
        # Get user data from database
        phone = session_data.get('phone')
        user_data = db.find_user_by_contact(phone) if phone else None
        
        # Setup bot
        bot = AFHSyncBot()
        bot_state = session_data.get('bot_state', 'START').upper()
        try:
            bot.state = bot.state.__class__[bot_state]
        except KeyError:
            bot.state = bot.state.__class__['START']
        
        # Merge user data into bot data
        if user_data:
            bot.data.update(user_data)
        else:
            bot.data.update(session_data.get('bot_data', {}))
        
        # Use IntelligentMessageHandler for browser
        if session_id not in intelligent_handlers:
            intelligent_handlers[session_id] = IntelligentMessageHandler(bot)
        handler = intelligent_handlers[session_id]
        
        # Generate context-aware welcome message
        welcome_msg = generate_context_welcome(user_data, bot.data)
        
        await websocket.send_json({'type': 'bot_response', 'message': welcome_msg})
        SessionManager.update_session(session_id, bot.state.value, bot.data)
        
        # Message loop
        while True:
            data = await websocket.receive_json()
            
            if data['type'] == 'user_message':
                response = handler.process_with_intelligence(
                    data['message'],
                    bot.state.value,
                    bot.data.get('role')
                )
                
                SessionManager.update_session(session_id, bot.state.value, bot.data)
                await websocket.send_json({'type': 'bot_response', 'message': response})
    
    except WebSocketDisconnect:
        if session_id in active_connections:
            del active_connections[session_id]
        if session_id in intelligent_handlers:
            del intelligent_handlers[session_id]
    except Exception as e:
        logger.error(f"WS error: {e}", exc_info=True)
        await websocket.send_json({'type': 'error', 'message': 'Error occurred'})
        

@app.websocket("/ws/{session_id}")
async def websocket_endpoint_old(websocket: WebSocket, session_id: str):
    """WebSocket with AI"""
    await websocket.accept()
    active_connections[session_id] = websocket
    
    try:
        session = SessionManager.get_session(session_id)
        if not session:
            await websocket.send_json({'type': 'error', 'message': 'Session not found'})
            await websocket.close()
            return
        
        # Bot - FIX: Convert state to uppercase
        bot = AFHSyncBot()
        bot_state = session.get('bot_state', 'START').upper()  # Convert to uppercase
        try:
            bot.state = bot.state.__class__[bot_state]
        except KeyError:
            # If state is invalid, default to START
            bot.state = bot.state.__class__['START']
        
        bot.data = session.get('bot_data', {})
        
        # AI Handler
        if session_id not in intelligent_handlers:
            intelligent_handlers[session_id] = IntelligentMessageHandler(bot)
        handler = intelligent_handlers[session_id]
        
        # Welcome
        user_role = bot.data.get('role')
        if bot.state.value == 'START':
            msg = handler._handle_greeting('START', None)
        else:
            msg = handler.process_with_intelligence("continue", bot.state.value, user_role)
        
        await websocket.send_json({'type': 'bot_response', 'message': msg})
        SessionManager.update_session(session_id, bot.state.value, bot.data)
        
        # Loop
        while True:
            data = await websocket.receive_json()
            
            if data['type'] == 'user_message':
                response = handler.process_with_intelligence(
                    data['message'],
                    bot.state.value,
                    bot.data.get('role')
                )
                
                SessionManager.update_session(session_id, bot.state.value, bot.data)
                await websocket.send_json({'type': 'bot_response', 'message': response})
    
    except WebSocketDisconnect:
        if session_id in active_connections:
            del active_connections[session_id]
        if session_id in intelligent_handlers:
            del intelligent_handlers[session_id]
    except Exception as e:
        logger.error(f"WS error: {e}", exc_info=True)
        await websocket.send_json({'type': 'error', 'message': 'Error occurred'})


# In main.py - Replace generate_context_welcome with this

def generate_context_welcome(user_data: Optional[Dict], bot_data: Dict) -> str:
    """Generate personalized welcome based on user context - NO EMOJIS"""
    
    from datetime import datetime
    
    # Get current time for greeting
    current_hour = datetime.now().hour
    if current_hour < 12:
        time_greeting = "Good morning"
    elif current_hour < 17:
        time_greeting = "Good afternoon"
    else:
        time_greeting = "Good evening"
    
    # Get user name and city
    name = user_data.get('name') if user_data else bot_data.get('name')
    city = user_data.get('city') if user_data else bot_data.get('city')
    
    # Build personalized greeting
    if name and city:
        greeting = f"{time_greeting}, {name} from {city}!"
    elif name:
        greeting = f"{time_greeting}, {name}!"
    elif city:
        greeting = f"{time_greeting} from {city}!"
    else:
        greeting = f"{time_greeting}!"
    
    # If no user data, simple welcome
    if not user_data:
        return f"{greeting}\n\nWelcome to AFHSync! Let's get you set up."
    
    role = user_data.get('role')
    
    # Build context message based on role
    context_msg = greeting + "\n\n"
    
    # CAREGIVER CONTEXT
    if role == 'caregiver':
        certifications = user_data.get('certifications', [])
        availability_summary = user_data.get('availability_summary')
        
        profile_items = []
        if certifications:
            certs = ', '.join(certifications) if isinstance(certifications, list) else certifications
            profile_items.append(f"Certifications: {certs}")
        if availability_summary:
            profile_items.append(f"Availability: {availability_summary}")
        
        if profile_items:
            context_msg += "**Your Profile:**\n"
            context_msg += '\n'.join(profile_items)
            context_msg += "\n\n"
        
        context_msg += "**What would you like to do?**\n\n"
        context_msg += "[Browse job openings](#action:browse_jobs)\n"
        context_msg += "[Build your resume](#action:resume_builder)\n"
        context_msg += "[Complete your profile](#action:complete_profile)\n"
        context_msg += "[Upload certifications](#action:upload_certs)\n"
        context_msg += "[Update availability](#action:update_availability)\n\n"
        context_msg += "Click a link or describe what you need."
    
    # AFH PROVIDER CONTEXT
    elif role == 'afh_provider':
        num_facilities = user_data.get('number_of_facilities')
        facility_location = user_data.get('facility_location') or user_data.get('facility_city')
        capacity = user_data.get('capacity')
        
        facility_items = []
        if num_facilities:
            facility_items.append(f"Number of facilities: {num_facilities}")
        if facility_location:
            facility_items.append(f"Primary location: {facility_location}")
        if capacity:
            facility_items.append(f"Capacity: {capacity} residents")
        
        if facility_items:
            context_msg += "**Your Facilities:**\n"
            context_msg += '\n'.join(facility_items)
            context_msg += "\n\n"
        
        context_msg += "**Complete Your Setup:**\n\n"
        context_msg += "[Upload facility photos](#action:upload_photos)\n"
        context_msg += "[Post a job opening](#action:post_job)\n"
        context_msg += "[Add more facilities](#action:add_facility)\n"
        context_msg += "[Browse caregivers](#action:browse_caregivers)\n\n"
        context_msg += "What would you like to do?"
    
    # SERVICE PROVIDER CONTEXT
    elif role == 'service_provider':
        service_type = user_data.get('service_type')
        service_area = user_data.get('service_area')
        
        service_items = []
        if service_type:
            service_items.append(f"Service: {service_type}")
        if service_area:
            service_items.append(f"Area: {service_area}")
        
        if service_items:
            context_msg += "**Your Services:**\n"
            context_msg += '\n'.join(service_items)
            context_msg += "\n\n"
        
        context_msg += "**Complete Your Profile:**\n\n"
        context_msg += "[Upload service brochures](#action:upload_brochures)\n"
        context_msg += "[Add photos/portfolio](#action:upload_portfolio)\n"
        context_msg += "[Browse AFH requests](#action:browse_requests)\n\n"
        context_msg += "What would you like to do?"
    
    # NO ROLE YET
    else:
        context_msg += "Welcome to AFHSync!\n\n"
        context_msg += "I see we started your registration. Are you a:\n\n"
        context_msg += "[Caregiver](#action:select_role_caregiver) - Looking for jobs\n"
        context_msg += "[AFH Owner](#action:select_role_afh) - Hiring caregivers\n"
        context_msg += "[Service Provider](#action:select_role_service) - Offering services\n\n"
        context_msg += "Please select your role to continue."
    
    return context_msg
# API
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "redis": redis_client is not None,
        "sessions": len(active_connections)
    }


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    session = SessionManager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Not found")
    return session
# In main.py

@app.get("/api/analytics/tokens")
async def get_token_analytics(
    start_date: str = None,
    end_date: str = None
):
    """Get token usage analytics"""
    from analytics.dashboard import AnalyticsDashboard
    from datetime import datetime, timedelta
    
    end = datetime.fromisoformat(end_date) if end_date else datetime.utcnow()
    start = datetime.fromisoformat(start_date) if start_date else end - timedelta(days=7)
    
    dashboard = AnalyticsDashboard(db)
    return dashboard.get_token_usage_report(start, end)


@app.get("/api/analytics/conversations")
async def get_conversation_analytics(
    start_date: str = None,
    end_date: str = None
):
    """Get conversation metrics"""
    from analytics.dashboard import AnalyticsDashboard
    from datetime import datetime, timedelta
    
    end = datetime.fromisoformat(end_date) if end_date else datetime.utcnow()
    start = datetime.fromisoformat(start_date) if start_date else end - timedelta(days=7)
    
    dashboard = AnalyticsDashboard(db)
    return dashboard.get_conversation_metrics(start, end)


@app.get("/api/analytics/drop-offs")
async def get_drop_off_analytics():
    """Get drop-off analysis"""
    from analytics.dashboard import AnalyticsDashboard
    
    dashboard = AnalyticsDashboard(db)
    return dashboard.get_drop_off_analysis()

# @app.on_event("startup")
# async def startup():
#     logger.info("AFHSync Started")


# @app.on_event("shutdown")
# async def shutdown():
#     for ws in active_connections.values():
#         await ws.close()
#     active_connections.clear()
#     intelligent_handlers.clear()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)