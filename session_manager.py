from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from models import User, Organization, ChatSession, ChatMessage
import logging

logger = logging.getLogger(__name__)

class SessionManager:
    """Manages user sessions and authentication"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def authenticate_organization(self, api_key: str) -> Optional[Organization]:
        """Authenticate organization by API key"""
        try:
            org = self.db.query(Organization).filter(
                Organization.api_key == api_key,
                Organization.is_active == True
            ).first()
            return org
        except Exception as e:
            logger.error(f"Error authenticating organization: {e}")
            return None
    
    def get_or_create_user(self, username: str, organization: Organization, email: str = None) -> User:
        """Get existing user or create new one"""
        try:
            user = self.db.query(User).filter(
                User.username == username,
                User.organization_id == organization.id,
                User.is_active == True
            ).first()
            
            if not user:
                user = User(
                    username=username,
                    email=email,
                    organization_id=organization.id
                )
                self.db.add(user)
                self.db.commit()
                logger.info(f"Created new user: {username} for org: {organization.name}")
            else:
                # Update last active
                user.last_active = datetime.utcnow()
                self.db.commit()
            
            return user
        except Exception as e:
            logger.error(f"Error getting/creating user: {e}")
            self.db.rollback()
            raise
    
    def create_session(self, user: User) -> ChatSession:
        """Create new chat session"""
        try:
            # Deactivate old sessions
            old_sessions = self.db.query(ChatSession).filter(
                ChatSession.user_id == user.id,
                ChatSession.is_active == True
            ).all()
            
            for session in old_sessions:
                session.is_active = False
            
            # Create new session
            new_session = ChatSession(
                user_id=user.id,
                organization_id=user.organization_id,
                expires_at=datetime.utcnow() + timedelta(hours=24)
            )
            
            self.db.add(new_session)
            self.db.commit()
            
            logger.info(f"Created new session for user: {user.username}")
            return new_session
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            self.db.rollback()
            raise
    
    def get_active_session(self, session_token: str) -> Optional[ChatSession]:
        """Get active session by token"""
        try:
            session = self.db.query(ChatSession).filter(
                ChatSession.session_token == session_token,
                ChatSession.is_active == True,
                ChatSession.expires_at > datetime.utcnow()
            ).first()
            
            if session:
                # Update last activity
                session.last_activity = datetime.utcnow()
                self.db.commit()
            
            return session
        except Exception as e:
            logger.error(f"Error getting session: {e}")
            return None
    
    def save_message(self, session: ChatSession, message_type: str, content: str, sources: list = None):
        """Save chat message to database"""
        try:
            message = ChatMessage(
                session_id=session.id,
                message_type=message_type,
                content=content
            )
            
            if sources:
                message.set_sources(sources)
            
            self.db.add(message)
            self.db.commit()
            
            return message
        except Exception as e:
            logger.error(f"Error saving message: {e}")
            self.db.rollback()
            raise
    
    def get_conversation_history(self, session: ChatSession, limit: int = 10) -> list:
        """Get recent conversation history"""
        try:
            messages = self.db.query(ChatMessage).filter(
                ChatMessage.session_id == session.id
            ).order_by(ChatMessage.timestamp.desc()).limit(limit * 2).all()
            
            # Convert to chat format
            history = []
            for msg in reversed(messages):
                history.append({
                    "role": "user" if msg.message_type == "user" else "assistant",
                    "content": msg.content,
                    "sources": msg.get_sources() if msg.message_type == "assistant" else None,
                    "timestamp": msg.timestamp.isoformat()
                })
            
            return history[-limit*2:] if len(history) > limit*2 else history
        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return []
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        try:
            expired_sessions = self.db.query(ChatSession).filter(
                ChatSession.expires_at < datetime.utcnow(),
                ChatSession.is_active == True
            ).all()
            
            for session in expired_sessions:
                session.is_active = False
            
            self.db.commit()
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
        except Exception as e:
            logger.error(f"Error cleaning up sessions: {e}")
            self.db.rollback()