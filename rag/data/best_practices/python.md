"""
Python Best Practices - Example Content
"""
# Python Best Practices

## Function Design

### Keep Functions Small and Focused
Functions should do one thing and do it well. Aim for functions that are:
- Less than 20 lines
- Have a single responsibility
- Are easily testable

**Bad:**
```python
def process_user_data(user_id):
    # Fetch user
    user = db.get_user(user_id)
    # Validate
    if not user.email:
        raise ValueError("No email")
    # Process
    result = expensive_computation(user)
    # Send email
    send_email(user.email, result)
    # Log
    logger.info(f"Processed {user_id}")
    return result
```

**Good:**
```python
def process_user_data(user_id):
    user = fetch_and_validate_user(user_id)
    result = compute_user_result(user)
    notify_user(user, result)
    return result
```

## Error Handling

### Use Specific Exceptions
Catch specific exceptions rather than bare `except:` clauses.

**Bad:**
```python
try:
    process_data()
except:
    pass  # Silent failure!
```

**Good:**
```python
try:
    process_data()
except ValueError as e:
    logger.error(f"Invalid data: {e}")
    raise
except DatabaseError as e:
    logger.error(f"Database error: {e}")
    # Handle or re-raise
```

## Type Hints

### Use Type Hints for Public APIs
Type hints improve code clarity and enable static analysis.

```python
from typing import List, Optional

def find_users(
    name: str, 
    age: Optional[int] = None
) -> List[User]:
    """Find users by name and optionally age."""
    ...
```

## Performance

### Use List Comprehensions
List comprehensions are faster than loops for simple transformations.

**Slow:**
```python
result = []
for item in items:
    if item.valid:
        result.append(item.value)
```

**Fast:**
```python
result = [item.value for item in items if item.valid]
```