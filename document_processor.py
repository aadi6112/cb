import os
import logging
from typing import List
from langchain_community.document_loaders import (
    PyPDFLoader, 
    TextLoader, 
    Docx2txtLoader,
    UnstructuredMarkdownLoader
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.schema import Document
from langchain.embeddings.base import Embeddings
import requests
from config import Config

logger = logging.getLogger(__name__)

class UniversalEmbeddings(Embeddings):
    """Universal embeddings class that works with both OpenAI and AIMLAPI"""
    
    def __init__(self, api_key: str, model_name: str, base_url: str, is_openai: bool = True):
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url
        self.is_openai = is_openai
        self.api_url = f"{base_url}/embeddings"
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents"""
        embeddings = []
        # Process in batches to avoid rate limits
        batch_size = 10
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = self._get_embeddings(batch)
            embeddings.extend(batch_embeddings)
        return embeddings
    
    def embed_query(self, text: str) -> List[float]:
        """Embed a single query"""
        embeddings = self._get_embeddings([text])
        return embeddings[0] if embeddings else []
    
    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for multiple texts"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model_name,
                "input": texts
            }
            
            response = requests.post(
                self.api_url,
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"Embedding API request failed: {response.text}")
                # Return dummy embeddings if API fails
                return [[0.0] * 1536 for _ in texts]
            
            result = response.json()
            embeddings = [item['embedding'] for item in result['data']]
            return embeddings
            
        except Exception as e:
            logger.error(f"Error getting embeddings: {str(e)}")
            # Return dummy embeddings if error occurs
            return [[0.0] * 1536 for _ in texts]

class DocumentProcessor:
    """Handles document loading and processing for the RAG system"""
    
    def __init__(self):
        """Initialize the document processor"""
        self.embeddings = UniversalEmbeddings(
            api_key=Config.API_KEY,
            model_name=Config.EMBEDDING_MODEL,
            base_url=Config.BASE_URL,
            is_openai=Config.USE_OPENAI
        )
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=Config.CHUNK_SIZE,
            chunk_overlap=Config.CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        
        # Supported file extensions and their loaders
        self.loaders = {
            '.pdf': PyPDFLoader,
            '.txt': TextLoader,
            '.docx': Docx2txtLoader,
            '.doc': Docx2txtLoader,
            '.md': UnstructuredMarkdownLoader
        }
    
    def load_document(self, file_path: str) -> List[Document]:
        """Load a single document"""
        try:
            file_extension = os.path.splitext(file_path)[1].lower()
            
            if file_extension not in self.loaders:
                logger.warning(f"Unsupported file type: {file_extension} for file: {file_path}")
                return []
            
            loader_class = self.loaders[file_extension]
            loader = loader_class(file_path)
            documents = loader.load()
            
            # Add metadata
            for doc in documents:
                doc.metadata['source'] = os.path.basename(file_path)
                doc.metadata['file_type'] = file_extension
            
            logger.info(f"Successfully loaded {file_path} with {len(documents)} pages/sections")
            return documents
            
        except Exception as e:
            logger.error(f"Error loading document {file_path}: {str(e)}")
            return []
    
    def load_all_documents(self, directory_path: str) -> List[Document]:
        """Load all documents from a directory"""
        all_documents = []
        
        try:
            for root, dirs, files in os.walk(directory_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    file_extension = os.path.splitext(file)[1].lower()
                    
                    if file_extension in self.loaders:
                        documents = self.load_document(file_path)
                        all_documents.extend(documents)
            
            logger.info(f"Loaded {len(all_documents)} documents from {directory_path}")
            return all_documents
            
        except Exception as e:
            logger.error(f"Error loading documents from directory: {str(e)}")
            return []
    
    def split_documents(self, documents: List[Document]) -> List[Document]:
        """Split documents into chunks"""
        try:
            splits = self.text_splitter.split_documents(documents)
            logger.info(f"Split documents into {len(splits)} chunks")
            return splits
        except Exception as e:
            logger.error(f"Error splitting documents: {str(e)}")
            return []
    
    def create_vectorstore(self, documents: List[Document]) -> FAISS:
        """Create FAISS vectorstore from documents"""
        try:
            if not documents:
                raise ValueError("No documents to create vectorstore from")
            
            vectorstore = FAISS.from_documents(
                documents=documents,
                embedding=self.embeddings
            )
            
            # Save vectorstore
            vectorstore.save_local(Config.VECTOR_STORE_PATH)
            logger.info(f"Created and saved vectorstore with {len(documents)} chunks")
            
            return vectorstore
            
        except Exception as e:
            logger.error(f"Error creating vectorstore: {str(e)}")
            raise
    
    def load_vectorstore(self) -> FAISS:
        """Load existing vectorstore"""
        try:
            if os.path.exists(Config.VECTOR_STORE_PATH):
                vectorstore = FAISS.load_local(
                    Config.VECTOR_STORE_PATH,
                    self.embeddings,
                    allow_dangerous_deserialization=True
                )
                logger.info("Loaded existing vectorstore")
                return vectorstore
            else:
                logger.warning("No existing vectorstore found")
                return None
                
        except Exception as e:
            logger.error(f"Error loading vectorstore: {str(e)}")
            return None
    
    def load_and_process_documents(self, directory_path: str) -> FAISS:
        """Main method to load and process all documents"""
        try:
            # Check if vectorstore already exists
            existing_vectorstore = self.load_vectorstore()
            
            # Load all documents
            documents = self.load_all_documents(directory_path)
            
            if not documents:
                if existing_vectorstore:
                    logger.info("No new documents found, using existing vectorstore")
                    return existing_vectorstore
                else:
                    raise ValueError("No documents found to process")
            
            # Split documents
            splits = self.split_documents(documents)
            
            if not splits:
                raise ValueError("No document chunks created")
            
            # Create vectorstore
            vectorstore = self.create_vectorstore(splits)
            
            return vectorstore
            
        except Exception as e:
            logger.error(f"Error in load_and_process_documents: {str(e)}")
            raise