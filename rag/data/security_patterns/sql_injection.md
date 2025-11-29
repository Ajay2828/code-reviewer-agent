"""
SQL Injection Prevention
"""
# Preventing SQL Injection

## Overview
SQL injection occurs when untrusted user input is concatenated directly into SQL queries.

## Always Use Parameterized Queries

### Python (with SQLAlchemy)
**Vulnerable:**
```python
query = f"SELECT * FROM users WHERE id = {user_id}"
result = db.execute(query)
```

**Secure:**
```python
from sqlalchemy import text
query = text("SELECT * FROM users WHERE id = :user_id")
result = db.execute(query, {"user_id": user_id})
```

### JavaScript (with PostgreSQL)
**Vulnerable:**
```javascript
const query = `SELECT * FROM users WHERE email = '${email}'`;
```

**Secure:**
```javascript
const query = 'SELECT * FROM users WHERE email = $1';
const result = await pool.query(query, [email]);
```

## Use ORM Features
Modern ORMs provide protection:

```python
# SQLAlchemy
user = User.query.filter_by(email=email).first()

# Django
user = User.objects.filter(email=email).first()
```

## Input Validation
Always validate and sanitize inputs:

```python
def is_valid_email(email: str) -> bool:
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))
```

# ============================================================
