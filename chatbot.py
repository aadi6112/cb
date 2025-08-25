import logging
from typing import List, Dict, Any, Optional
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferWindowMemory
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langchain_community.vectorstores import FAISS
from models import ChatSession
from config import Config
import requests
from langchain.llms.base import LLM
from langchain.callbacks.manager import CallbackManagerForLLMRun

logger = logging.getLogger(__name__)

class UniversalLLM(LLM):
    """Universal LLM wrapper for both OpenAI and AIMLAPI"""
    
    api_key: str = Config.API_KEY
    model_name: str = Config.MODEL_NAME
    temperature: float = Config.TEMPERATURE
    max_tokens: int = Config.MAX_TOKENS
    base_url: str = Config.BASE_URL
    is_openai: bool = Config.USE_OPENAI
    
    @property
    def _llm_type(self) -> str:
        return "openai" if self.is_openai else "aimlapi"
    
    def _call(
        self,
        prompt: str,
        stop: List[str] = None,
        run_manager: CallbackManagerForLLMRun = None,
        **kwargs: Any,
    ) -> str:
        """Call the API to get response"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": Config.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            }
            
            if stop:
                data["stop"] = stop
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code != 200:
                error_msg = f"API request failed with status {response.status_code}: {response.text}"
                logger.error(error_msg)
                return f"I apologize, but I encountered an error processing your request. Please try again."
            
            result = response.json()
            return result['choices'][0]['message']['content']
            
        except Exception as e:
            logger.error(f"Error calling API: {str(e)}")
            return f"I apologize, but I encountered an error: {str(e)}"

class SessionAwareChatbot:
    """Enhanced chatbot with session and multi-user support"""
    
    def __init__(self, vectorstore: FAISS):
        """Initialize the chatbot with a vectorstore"""
        self.vectorstore = vectorstore
        self.llm = UniversalLLM()
        self._sessions = {}  # In-memory session cache
    
    def get_or_create_memory(self, session_id: str, conversation_history: List[Dict] = None):
        """Get or create conversation memory for a session"""
        if session_id not in self._sessions:
            memory = ConversationBufferWindowMemory(
                memory_key="chat_history",
                return_messages=True,
                output_key="answer",
                k=Config.MAX_CONTEXT_MESSAGES
            )
            
            # Load conversation history if provided
            if conversation_history:
                for msg in conversation_history:
                    if msg["role"] == "user":
                        memory.chat_memory.add_user_message(msg["content"])
                    elif msg["role"] == "assistant":
                        memory.chat_memory.add_ai_message(msg["content"])
            
            self._sessions[session_id] = {
                'memory': memory,
                'chain': ConversationalRetrievalChain.from_llm(
                    llm=self.llm,
                    retriever=self.vectorstore.as_retriever(
                        search_type="similarity",
                        search_kwargs={"k": 4}
                    ),
                    memory=memory,
                    return_source_documents=True,
                    verbose=True
                )
            }
        
        return self._sessions[session_id]
    
    def get_response(self, query: str, session_id: str, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """Get response for a user query with session context"""
        try:
            # Validate input
            if not query or not query.strip():
                return {
                    "response": "Please provide a valid question.",
                    "sources": [],
                    "success": False
                }
            
            # Get session context
            session_data = self.get_or_create_memory(session_id, conversation_history)
            chain = session_data['chain']
            
            # Get response from the chain
            result = chain({"question": query})
            
            # Extract answer and source documents
            answer = result.get("answer", "I couldn't find an answer to your question.")
            source_docs = result.get("source_documents", [])
            
            # Extract sources
            sources = []
            if source_docs:
                source_set = set()
                for doc in source_docs:
                    if 'source' in doc.metadata:
                        source_set.add(doc.metadata['source'])
                sources = list(source_set)
            
            return {
                "response": answer,
                "sources": sources,
                "success": True,
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"Error getting response for session {session_id}: {str(e)}")
            return {
                "response": "I apologize, but I encountered an error processing your request. Please try again.",
                "sources": [],
                "success": False,
                "error": str(e)
            }
    
    def clear_session_memory(self, session_id: str):
        """Clear conversation memory for a specific session"""
        try:
            if session_id in self._sessions:
                del self._sessions[session_id]
                logger.info(f"Cleared memory for session: {session_id}")
        except Exception as e:
            logger.error(f"Error clearing session memory: {str(e)}")
    
    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs"""
        return list(self._sessions.keys())