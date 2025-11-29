import os
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
import structlog

from config.settings import get_settings

logger = structlog.get_logger()
settings = get_settings()


class KnowledgeBase:
    """
    RAG system for retrieving best practices and coding patterns
    
    Stores:
    - Language-specific best practices
    - Security guidelines
    - Performance optimization patterns
    - Common bug patterns and fixes
    """
    
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            openai_api_key=settings.OPENAI_API_KEY
        )
        
        # Initialize ChromaDB
        self.chroma_client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR
        )
        
        # Create or get collections
        self.collections = {
            "best_practices": self._get_or_create_collection("best_practices"),
            "security_patterns": self._get_or_create_collection("security_patterns"),
            "performance_tips": self._get_or_create_collection("performance_tips"),
            "bug_patterns": self._get_or_create_collection("bug_patterns"),
        }
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", " ", ""]
        )
    
    def _get_or_create_collection(self, name: str):
        """Get or create a ChromaDB collection"""
        try:
            return self.chroma_client.get_collection(name=name)
        except:
            return self.chroma_client.create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"}
            )
    
    async def initialize_from_files(self, data_dir: str):
        """
        Load best practices from markdown files into vector store
        
        Expected directory structure:
        data_dir/
            best_practices/
                python.md
                javascript.md
            security_patterns/
                sql_injection.md
                xss_prevention.md
            performance_tips/
                database_optimization.md
            bug_patterns/
                common_errors.md
        """
        logger.info("initializing_knowledge_base", data_dir=data_dir)
        
        for collection_name, collection in self.collections.items():
            collection_dir = os.path.join(data_dir, collection_name)
            
            if not os.path.exists(collection_dir):
                logger.warning(
                    "collection_directory_not_found",
                    directory=collection_dir
                )
                continue
            
            # Load all markdown files
            documents = []
            for filename in os.listdir(collection_dir):
                if filename.endswith('.md'):
                    filepath = os.path.join(collection_dir, filename)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                        # Extract metadata from filename
                        topic = filename.replace('.md', '')
                        
                        documents.append(Document(
                            page_content=content,
                            metadata={
                                "source": filename,
                                "topic": topic,
                                "collection": collection_name
                            }
                        ))
            
            if documents:
                # Split documents
                split_docs = self.text_splitter.split_documents(documents)
                
                # Add to collection
                texts = [doc.page_content for doc in split_docs]
                metadatas = [doc.metadata for doc in split_docs]
                ids = [f"{collection_name}_{i}" for i in range(len(texts))]
                
                # Generate embeddings and add
                embeddings_list = self.embeddings.embed_documents(texts)
                
                collection.add(
                    embeddings=embeddings_list,
                    documents=texts,
                    metadatas=metadatas,
                    ids=ids
                )
                
                logger.info(
                    "collection_loaded",
                    collection=collection_name,
                    documents=len(split_docs)
                )
    
    async def retrieve_best_practices(
        self,
        query: str,
        language: Optional[str] = None,
        category: Optional[str] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant best practices for a query
        
        Args:
            query: Search query (e.g., "how to prevent SQL injection")
            language: Filter by programming language
            category: Filter by category (best_practices, security_patterns, etc.)
            top_k: Number of results to return
        
        Returns:
            List of relevant documents with content and metadata
        """
        try:
            # Generate query embedding
            query_embedding = self.embeddings.embed_query(query)
            
            # Determine which collections to search
            collections_to_search = []
            if category and category in self.collections:
                collections_to_search = [self.collections[category]]
            else:
                collections_to_search = list(self.collections.values())
            
            all_results = []
            
            for collection in collections_to_search:
                # Build filter
                where_filter = {}
                if language:
                    where_filter["topic"] = language
                
                # Query collection
                results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=top_k,
                    where=where_filter if where_filter else None
                )
                
                # Process results
                if results['documents']:
                    for i, doc in enumerate(results['documents'][0]):
                        all_results.append({
                            "content": doc,
                            "metadata": results['metadatas'][0][i],
                            "distance": results['distances'][0][i]
                        })
            
            # Sort by distance and return top_k
            all_results.sort(key=lambda x: x['distance'])
            return all_results[:top_k]
            
        except Exception as e:
            logger.error("retrieve_best_practices_failed", error=str(e))
            return []
    
    async def retrieve_for_issue(
        self,
        issue_description: str,
        language: str,
        category: str
    ) -> List[Dict[str, Any]]:
        """
        Retrieve best practices specific to an issue
        
        Maps issue categories to collections:
        - bug -> bug_patterns
        - security -> security_patterns
        - performance -> performance_tips
        - style/documentation -> best_practices
        """
        collection_map = {
            "bug": "bug_patterns",
            "security": "security_patterns",
            "performance": "performance_tips",
            "style": "best_practices",
            "documentation": "best_practices",
            "best_practice": "best_practices"
        }
        
        collection_name = collection_map.get(category, "best_practices")
        
        return await self.retrieve_best_practices(
            query=issue_description,
            language=language,
            category=collection_name,
            top_k=3
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the knowledge base"""
        stats = {}
        for name, collection in self.collections.items():
            stats[name] = collection.count()
        return stats


# Singleton instance
_knowledge_base: Optional[KnowledgeBase] = None


def get_knowledge_base() -> KnowledgeBase:
    """Get or create knowledge base instance"""
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = KnowledgeBase()
    return _knowledge_base