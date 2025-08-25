from datetime import datetime, timedelta
import uuid
from sqlalchemy import create_engine, Column, String, DateTime, Text, Integer, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import json

Base = declarative_base()

class Organization(Base):
    __tablename__ = 'organizations'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    domain = Column(String(255), unique=True)
    api_key = Column(String(255), unique=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    users = relationship("User", back_populates="organization")
    sessions = relationship("ChatSession", back_populates="organization")

class User(Base):
    __tablename__ = 'users'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(255), nullable=False)
    email = Column(String(255))
    organization_id = Column(String(36), ForeignKey('organizations.id'))
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    organization = relationship("Organization", back_populates="users")
    sessions = relationship("ChatSession", back_populates="user")

class ChatSession(Base):
    __tablename__ = 'chat_sessions'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'))
    organization_id = Column(String(36), ForeignKey('organizations.id'))
    session_token = Column(String(255), unique=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(hours=24))
    is_active = Column(Boolean, default=True)
    context_data = Column(Text)  # JSON string for conversation context
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    organization = relationship("Organization", back_populates="sessions")
    messages = relationship("ChatMessage", back_populates="session")
    
    def get_context(self):
        return json.loads(self.context_data) if self.context_data else {}
    
    def set_context(self, context):
        self.context_data = json.dumps(context)

class ChatMessage(Base):
    __tablename__ = 'chat_messages'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey('chat_sessions.id'))
    message_type = Column(String(20))  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    sources = Column(Text)  # JSON string for source citations
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    session = relationship("ChatSession", back_populates="messages")
    
    def get_sources(self):
        return json.loads(self.sources) if self.sources else []
    
    def set_sources(self, sources):
        self.sources = json.dumps(sources)

# Database setup
def create_database(database_url="sqlite:///hr_chatbot.db"):
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, SessionLocal