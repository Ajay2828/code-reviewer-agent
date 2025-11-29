# scripts/seed_knowledge_base.py
"""
Seed the knowledge base with best practices
"""
import asyncio
import os
from rag.knowledge_base import get_knowledge_base

async def seed_knowledge_base():
    """Load all best practices into vector store"""
    kb = get_knowledge_base()
    
    # Path to data directory
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'rag', 'data')
    
    print("🌱 Seeding knowledge base...")
    print(f"📁 Data directory: {data_dir}")
    
    # Create directories if they don't exist
    os.makedirs(os.path.join(data_dir, 'best_practices'), exist_ok=True)
    os.makedirs(os.path.join(data_dir, 'security_patterns'), exist_ok=True)
    os.makedirs(os.path.join(data_dir, 'performance_tips'), exist_ok=True)
    os.makedirs(os.path.join(data_dir, 'bug_patterns'), exist_ok=True)
    
    # Initialize from files
    await kb.initialize_from_files(data_dir)
    
    # Print stats
    stats = kb.get_stats()
    print("\n✅ Knowledge base seeded successfully!")
    print(f"📊 Statistics:")
    for collection, count in stats.items():
        print(f"   - {collection}: {count} documents")

if __name__ == "__main__":
    asyncio.run(seed_knowledge_base())