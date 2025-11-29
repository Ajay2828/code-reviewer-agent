# scripts/setup_db.py
"""
Setup database tables
"""
from sqlalchemy import create_engine
from db.models import Base
from config.settings import get_settings

settings = get_settings()

def setup_database():
    """Create all database tables"""
    print("🗄️  Setting up database...")
    
    engine = create_engine(settings.DATABASE_URL)
    Base.metadata.create_all(engine)
    
    print("✅ Database setup complete!")

if __name__ == "__main__":
    setup_database()