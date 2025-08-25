import os
import ssl
from flask import Flask, request, jsonify, render_template, g
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from functools import wraps
import logging
from datetime import datetime, timedelta

from models import create_database, Organization, User, ChatSession, ChatMessage
from session_manager import SessionManager
from document_processor import DocumentProcessor
from chatbot import SessionAwareChatbot
from config import Config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY
CORS(app, origins=Config.CORS_ORIGINS)

# Rate limiting - FIXED initialization
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[f"{Config.RATE_LIMIT_PER_MINUTE} per minute"],
    storage_uri="memory://"
)

# Global components
engine, SessionLocal = create_database(Config.DATABASE_URL)
doc_processor = None
chatbot = None

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        return db
    finally:
        pass

@app.before_request
def before_request():
    g.db = get_db()

@app.teardown_appcontext
def close_db(error):
    db = getattr(g, 'db', None)
    if db is not None:
        db.close()

def require_api_key(f):
    """Decorator to require API key authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        if not api_key:
            return jsonify({"error": "API key required"}), 401
        
        session_manager = SessionManager(g.db)
        organization = session_manager.authenticate_organization(api_key)
        if not organization:
            return jsonify({"error": "Invalid API key"}), 401
        
        g.organization = organization
        return f(*args, **kwargs)
    
    return decorated_function

def require_session(f):
    """Decorator to require valid session"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_token = request.headers.get('X-Session-Token')
        if not session_token and request.is_json:
            session_token = request.json.get('session_token')
        
        if not session_token:
            return jsonify({"error": "Session token required"}), 401
        
        session_manager = SessionManager(g.db)
        session = session_manager.get_active_session(session_token)
        if not session:
            return jsonify({"error": "Invalid or expired session"}), 401
        
        g.session = session
        return f(*args, **kwargs)
    
    return decorated_function

def initialize_app():
    """Initialize the application components"""
    global doc_processor, chatbot
    
    try:
        Config.validate()
        doc_processor = DocumentProcessor()
        
        documents_path = Config.DOCUMENTS_PATH
        if os.path.exists(documents_path):
            logger.info(f"Loading documents from {documents_path}")
            vectorstore = doc_processor.load_and_process_documents(documents_path)
            chatbot = SessionAwareChatbot(vectorstore)
            logger.info("Chatbot initialized successfully")
        else:
            logger.error(f"Documents path {documents_path} does not exist")
            raise Exception("Documents folder not found")
            
    except Exception as e:
        logger.error(f"Error initializing application: {str(e)}")
        raise

# ===== MAIN ROUTES =====

@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')

@app.route('/admin')
def admin_dashboard():
    """Serve the admin dashboard"""
    return render_template('admin.html')

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy", 
        "message": "HR Chatbot Multi-User API is running",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0",
        "components": {
            "database": "initialized" if SessionLocal else "not initialized",
            "chatbot": "ready" if chatbot else "not ready",
            "document_processor": "ready" if doc_processor else "not ready"
        }
    })

# ===== AUTHENTICATION API =====

@app.route('/api/v1/auth/login', methods=['POST'])
@limiter.limit("10 per minute")
@require_api_key
def login():
    """Create user session"""
    try:
        data = request.json or {}
        username = data.get('username')
        
        if not username:
            return jsonify({"error": "Username is required"}), 400
        
        email = data.get('email')
        session_manager = SessionManager(g.db)
        
        # Get or create user
        user = session_manager.get_or_create_user(username, g.organization, email)
        
        # Create session
        session = session_manager.create_session(user)
        
        return jsonify({
            "session_token": session.session_token,
            "user_id": user.id,
            "username": user.username,
            "organization": g.organization.name,
            "expires_at": session.expires_at.isoformat(),
            "success": True
        })
        
    except Exception as e:
        logger.error(f"Error in login: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/v1/auth/logout', methods=['POST'])
@require_session
def logout():
    """End user session"""
    try:
        g.session.is_active = False
        g.db.commit()
        
        if chatbot:
            chatbot.clear_session_memory(g.session.id)
        
        return jsonify({
            "message": "Session ended successfully",
            "success": True
        })
        
    except Exception as e:
        logger.error(f"Error in logout: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

# ===== CHAT API =====

@app.route('/api/v1/chat/message', methods=['POST'])
@limiter.limit("30 per minute")
@require_session
def chat_message():
    """Send chat message"""
    try:
        data = request.json or {}
        user_message = data.get('message')
        
        if not user_message:
            return jsonify({"error": "Message is required"}), 400
        
        if not chatbot:
            return jsonify({"error": "Chatbot not initialized"}), 500
        
        include_history = data.get('include_history', True)
        session_manager = SessionManager(g.db)
        
        # Get conversation history if requested
        conversation_history = []
        if include_history:
            conversation_history = session_manager.get_conversation_history(
                g.session, 
                limit=Config.MAX_CONTEXT_MESSAGES
            )
        
        # Save user message
        user_msg = session_manager.save_message(g.session, "user", user_message)
        
        # Get AI response
        result = chatbot.get_response(
            user_message, 
            g.session.id, 
            conversation_history
        )
        
        if result['success']:
            # Save assistant message
            assistant_msg = session_manager.save_message(
                g.session, 
                "assistant", 
                result['response'],
                result['sources']
            )
            
            return jsonify({
                "response": result['response'],
                "sources": result['sources'],
                "message_id": assistant_msg.id,
                "session_id": g.session.id,
                "timestamp": assistant_msg.timestamp.isoformat(),
                "success": True
            })
        else:
            return jsonify({
                "error": "Failed to get response",
                "details": result.get('error', 'Unknown error'),
                "success": False
            }), 500
        
    except Exception as e:
        logger.error(f"Error in chat message: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/v1/chat/history', methods=['GET'])
@require_session
def chat_history():
    """Get chat history for current session"""
    try:
        limit = min(int(request.args.get('limit', 50)), 100)
        
        session_manager = SessionManager(g.db)
        messages = session_manager.get_conversation_history(g.session, limit)
        
        return jsonify({
            "messages": messages,
            "total": len(messages),
            "session_id": g.session.id,
            "success": True
        })
        
    except Exception as e:
        logger.error(f"Error getting chat history: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/v1/chat/clear', methods=['POST'])
@require_session
def clear_chat():
    """Clear chat history for current session"""
    try:
        if chatbot:
            chatbot.clear_session_memory(g.session.id)
        
        return jsonify({
            "message": "Chat context cleared successfully",
            "success": True
        })
        
    except Exception as e:
        logger.error(f"Error clearing chat: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

# ===== ADMIN API =====

@app.route('/api/v1/admin/sessions', methods=['GET'])
@require_api_key
def list_sessions():
    """List active sessions for organization"""
    try:
        sessions = g.db.query(ChatSession).join(User).filter(
            ChatSession.organization_id == g.organization.id,
            ChatSession.is_active == True
        ).all()
        
        session_list = []
        for session in sessions:
            session_list.append({
                "session_id": session.id,
                "session_token": session.session_token,
                "user_id": session.user.id,
                "username": session.user.username,
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat(),
                "expires_at": session.expires_at.isoformat()
            })
        
        return jsonify({
            "sessions": session_list,
            "total": len(session_list),
            "organization": g.organization.name,
            "success": True
        })
        
    except Exception as e:
        logger.error(f"Error listing sessions: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/v1/admin/users', methods=['GET'])
@require_api_key
def list_users():
    """List all users for organization"""
    try:
        from sqlalchemy import func
        
        # Get users with session count
        users_query = g.db.query(
            User,
            func.count(ChatSession.id).label('session_count')
        ).outerjoin(
            ChatSession,
            (ChatSession.user_id == User.id) & (ChatSession.is_active == True)
        ).filter(
            User.organization_id == g.organization.id
        ).group_by(User.id).all()
        
        user_list = []
        for user, session_count in users_query:
            user_list.append({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "created_at": user.created_at.isoformat(),
                "last_active": user.last_active.isoformat() if user.last_active else None,
                "is_active": user.is_active,
                "session_count": session_count
            })
        
        return jsonify({
            "users": user_list,
            "total": len(user_list),
            "organization": g.organization.name,
            "success": True
        })
        
    except Exception as e:
        logger.error(f"Error listing users: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/v1/admin/users/<user_id>/sessions', methods=['GET'])
@require_api_key
def list_user_sessions(user_id):
    """Get all sessions for a specific user"""
    try:
        sessions = g.db.query(ChatSession).filter(
            ChatSession.user_id == user_id,
            ChatSession.organization_id == g.organization.id
        ).order_by(ChatSession.created_at.desc()).all()
        
        session_list = []
        for session in sessions:
            session_list.append({
                "session_id": session.id,
                "session_token": session.session_token,
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat(),
                "expires_at": session.expires_at.isoformat(),
                "is_active": session.is_active
            })
        
        return jsonify({
            "sessions": session_list,
            "total": len(session_list),
            "success": True
        })
        
    except Exception as e:
        logger.error(f"Error listing user sessions: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/v1/admin/sessions/<session_id>/terminate', methods=['POST'])
@require_api_key
def terminate_session(session_id):
    """Terminate a specific session"""
    try:
        session = g.db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.organization_id == g.organization.id
        ).first()
        
        if not session:
            return jsonify({"error": "Session not found"}), 404
        
        session.is_active = False
        g.db.commit()
        
        if chatbot:
            chatbot.clear_session_memory(session_id)
        
        return jsonify({
            "message": "Session terminated successfully",
            "session_id": session_id,
            "success": True
        })
        
    except Exception as e:
        logger.error(f"Error terminating session: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/v1/admin/users/<user_id>/terminate-sessions', methods=['POST'])
@require_api_key
def terminate_user_sessions(user_id):
    """Terminate all sessions for a specific user"""
    try:
        sessions = g.db.query(ChatSession).filter(
            ChatSession.user_id == user_id,
            ChatSession.organization_id == g.organization.id,
            ChatSession.is_active == True
        ).all()
        
        terminated_count = 0
        for session in sessions:
            session.is_active = False
            if chatbot:
                chatbot.clear_session_memory(session.id)
            terminated_count += 1
        
        g.db.commit()
        
        return jsonify({
            "message": f"Terminated {terminated_count} sessions for user",
            "user_id": user_id,
            "terminated_sessions": terminated_count,
            "success": True
        })
        
    except Exception as e:
        logger.error(f"Error terminating user sessions: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/v1/admin/stats', methods=['GET'])
@require_api_key
def get_admin_stats():
    """Get organization statistics"""
    try:
        from sqlalchemy import func
        
        # Get current stats
        total_users = g.db.query(User).filter(
            User.organization_id == g.organization.id
        ).count()
        
        active_sessions = g.db.query(ChatSession).filter(
            ChatSession.organization_id == g.organization.id,
            ChatSession.is_active == True,
            ChatSession.expires_at > datetime.utcnow()
        ).count()
        
        # Messages today
        today = datetime.utcnow().date()
        messages_today = g.db.query(ChatMessage).join(ChatSession).filter(
            ChatSession.organization_id == g.organization.id,
            func.date(ChatMessage.timestamp) == today
        ).count()
        
        # Calculate average session duration
        recent_sessions = g.db.query(ChatSession).filter(
            ChatSession.organization_id == g.organization.id,
            ChatSession.created_at > datetime.utcnow() - timedelta(days=7)
        ).all()
        
        total_duration = 0
        active_session_count = 0
        
        for session in recent_sessions:
            if session.last_activity and session.created_at:
                duration = (session.last_activity - session.created_at).total_seconds() / 60
                total_duration += duration
                active_session_count += 1
        
        avg_duration = int(total_duration / active_session_count) if active_session_count > 0 else 0
        avg_session_duration = f"{avg_duration}m" if avg_duration > 0 else "N/A"
        
        return jsonify({
            "stats": {
                "total_users": total_users,
                "active_sessions": active_sessions,
                "messages_today": messages_today,
                "avg_session_duration": avg_session_duration,
                "organization": g.organization.name,
                "timestamp": datetime.utcnow().isoformat()
            },
            "success": True
        })
        
    except Exception as e:
        logger.error(f"Error getting admin stats: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/v1/admin/messages/recent', methods=['GET'])
@require_api_key
def get_recent_messages():
    """Get recent messages across all sessions"""
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        
        messages = g.db.query(ChatMessage).join(ChatSession).join(User).filter(
            ChatSession.organization_id == g.organization.id
        ).order_by(ChatMessage.timestamp.desc()).limit(limit).all()
        
        message_list = []
        for msg in messages:
            message_list.append({
                "id": msg.id,
                "user": msg.session.user.username,
                "session_id": msg.session_id,
                "type": msg.message_type,
                "content": msg.content[:200] + "..." if len(msg.content) > 200 else msg.content,
                "sources": msg.get_sources() if msg.message_type == "assistant" else [],
                "timestamp": msg.timestamp.isoformat()
            })
        
        return jsonify({
            "messages": message_list,
            "total": len(message_list),
            "success": True
        })
        
    except Exception as e:
        logger.error(f"Error getting recent messages: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/v1/admin/reload-documents', methods=['POST'])
@require_api_key
def reload_documents():
    """Reload documents and rebuild vector store"""
    try:
        global chatbot
        
        vectorstore = doc_processor.load_and_process_documents(Config.DOCUMENTS_PATH)
        chatbot = SessionAwareChatbot(vectorstore)
        
        if chatbot:
            for session_id in chatbot.get_active_sessions():
                chatbot.clear_session_memory(session_id)
        
        return jsonify({
            "message": "Documents reloaded successfully",
            "timestamp": datetime.utcnow().isoformat(),
            "success": True
        })
        
    except Exception as e:
        logger.error(f"Error reloading documents: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
    
    @app.route('/admin')
    def admin_dashboard():
        """Serve the admin dashboard"""
    return render_template('admin.html')

# ===== LEGACY COMPATIBILITY =====

@app.route('/chat', methods=['POST'])
def legacy_chat():
    """Legacy chat endpoint"""
    return jsonify({
        "response": "Please use the new API endpoints. Visit the main page to get started.",
        "migration_required": True
    })

# ===== ERROR HANDLERS =====

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({
        "error": "Rate limit exceeded",
        "message": "Too many requests. Please slow down.",
        "retry_after": str(e.retry_after)
    }), 429

@app.errorhandler(404)
def not_found_handler(e):
    return jsonify({
        "error": "Endpoint not found",
        "message": "The requested endpoint does not exist"
    }), 404

@app.errorhandler(500)
def internal_error_handler(e):
    return jsonify({
        "error": "Internal server error",
        "message": "An unexpected error occurred"
    }), 500

# ===== SSL AND STARTUP =====

def create_ssl_context():
    """Create SSL context for HTTPS"""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    
    try:
        if os.path.exists(Config.SSL_CERT) and os.path.exists(Config.SSL_KEY):
            context.load_cert_chain(Config.SSL_CERT, Config.SSL_KEY)
            logger.info("SSL certificates loaded successfully")
        else:
            logger.warning("SSL certificate files not found")
            return None
            
    except Exception as e:
        logger.error(f"Error loading SSL certificates: {str(e)}")
        return None
        
    return context

if __name__ == '__main__':
    try:
        initialize_app()
        ssl_context = create_ssl_context()
        
        if ssl_context:
            logger.info(f"Starting HR Chatbot Multi-User API on https://localhost:{Config.PORT}")
            app.run(host='0.0.0.0', port=Config.PORT, ssl_context=ssl_context, debug=Config.DEBUG)
        else:
            logger.info(f"Starting HR Chatbot Multi-User API on http://localhost:{Config.PORT}")
            app.run(host='0.0.0.0', port=Config.PORT, debug=Config.DEBUG)
        
    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}")
        raise