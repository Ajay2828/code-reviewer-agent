# rag/data/performance_tips/database.md
"""
Database Performance Optimization
"""
# Database Optimization Tips

## N+1 Query Problem

### The Problem
```python
# Fetches users (1 query)
users = User.query.all()

# For each user, fetches posts (N queries!)
for user in users:
    posts = user.posts  # Separate query!
```

### The Solution
```python
# Single query with JOIN
users = User.query.options(
    joinedload(User.posts)
).all()
```

## Indexing

### Add Indexes for Frequent Queries
```python
class User(Base):
    __tablename__ = 'users'
    
    email = Column(String, index=True)  # Frequently queried
    created_at = Column(DateTime, index=True)  # For sorting
```

### Composite Indexes
```python
# For queries that filter by both fields
Index('ix_user_email_status', User.email, User.status)
```

## Query Optimization

### Select Only Needed Columns
**Inefficient:**
```python
users = session.query(User).all()  # Fetches all columns
```

**Efficient:**
```python
users = session.query(User.id, User.name).all()
```

### Use Pagination
```python
# Instead of loading everything
users = User.query.limit(20).offset(page * 20).all()
```

## Connection Pooling
```python
from sqlalchemy import create_engine

engine = create_engine(
    'postgresql://...',
    pool_size=20,  # Maximum connections
    max_overflow=10,  # Extra connections when needed
    pool_timeout=30
)
```