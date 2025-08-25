import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Enhanced configuration for multi-user HR Chatbot"""
    
    # Database Configuration
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///hr_chatbot.db')
    
    # API Configuration
    USE_OPENAI = os.getenv('USE_OPENAI', 'True').lower() == 'true'
    
    # OpenAI Configuration
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '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')
    OPENAI_MODEL_NAME = os.getenv('OPENAI_MODEL_NAME', 'gpt-3.5-turbo')
    OPENAI_EMBEDDING_MODEL = os.getenv('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small')
    
    # AIMLAPI Configuration
    AIMLAPI_KEY = os.getenv('AIMLAPI_KEY', '')
    AIMLAPI_BASE_URL = "https://api.aimlapi.com/v1"
    AIMLAPI_MODEL_NAME = os.getenv('AIMLAPI_MODEL_NAME', 'mistralai/Mistral-7B-Instruct-v0.2')
    AIMLAPI_EMBEDDING_MODEL = os.getenv('AIMLAPI_EMBEDDING_MODEL', 'text-embedding-3-small')
    
    # Select active configuration
    if USE_OPENAI:
        API_KEY = OPENAI_API_KEY
        MODEL_NAME = OPENAI_MODEL_NAME
        EMBEDDING_MODEL = OPENAI_EMBEDDING_MODEL
        BASE_URL = "https://api.openai.com/v1"
    else:
        API_KEY = AIMLAPI_KEY
        MODEL_NAME = AIMLAPI_MODEL_NAME
        EMBEDDING_MODEL = AIMLAPI_EMBEDDING_MODEL
        BASE_URL = AIMLAPI_BASE_URL
    
    # Application Configuration
    PORT = int(os.getenv('PORT', 5000))
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-this')
    
    # Session Configuration
    SESSION_TIMEOUT_HOURS = int(os.getenv('SESSION_TIMEOUT_HOURS', 24))
    MAX_CONTEXT_MESSAGES = int(os.getenv('MAX_CONTEXT_MESSAGES', 10))
    
    # Document Configuration
    DOCUMENTS_PATH = os.path.join(os.path.dirname(__file__), 'documents')
    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 200
    VECTOR_STORE_PATH = os.path.join(os.path.dirname(__file__), 'vectorstore')
    
    # Chat Configuration
    MAX_CONTEXT_LENGTH = 4000
    TEMPERATURE = 0.7
    MAX_TOKENS = 500
    
    # SSL Configuration
    SSL_CERT = os.path.join(os.path.dirname(__file__), 'certificates', 'cert.pem')
    SSL_KEY = os.path.join(os.path.dirname(__file__), 'certificates', 'key.pem')
    
    # API Rate Limiting
    RATE_LIMIT_PER_MINUTE = int(os.getenv('RATE_LIMIT_PER_MINUTE', 60))
    
    # CORS Configuration
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*').split(',')
    
    # System Prompt
    SYSTEM_PROMPT = """You are an AI assistant specialized in HR policies and procedures. 
    You have access to the company's HR documentation and should provide accurate, helpful responses 
    based on the information available in these documents.
    
    Guidelines:
    1. Always base your answers on the provided HR documentation
    2. If information is not available in the documents, clearly state that
    3. Be professional, clear, and concise in your responses
    4. When citing policies, reference the specific section or document when possible
    5. If a question is unclear, ask for clarification
    
    Remember: You are representing the HR department, so maintain a professional and helpful tone."""

    @classmethod
    def validate(cls):
        """Validate configuration settings"""
        if cls.USE_OPENAI and not cls.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required when USE_OPENAI=True")
        if not cls.USE_OPENAI and not cls.AIMLAPI_KEY:
            raise ValueError("AIMLAPI_KEY is required when USE_OPENAI=False")
        
        # Create directories
        os.makedirs(cls.DOCUMENTS_PATH, exist_ok=True)
        os.makedirs(cls.VECTOR_STORE_PATH, exist_ok=True)
        os.makedirs(os.path.dirname(cls.SSL_CERT), exist_ok=True)
        
        return True