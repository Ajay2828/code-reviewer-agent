# 🚀 Getting Started Guide

This guide will walk you through setting up and running the AI Code Review Agent system from scratch.

## 📋 Prerequisites

Before you begin, ensure you have:

1. **Python 3.11+** installed
2. **API Keys**:
   - Anthropic API key (get from: https://console.anthropic.com)
   - OpenAI API key (get from: https://platform.openai.com)
3. **Optional**:
   - Docker & Docker Compose (for containerized deployment)
   - GitHub Personal Access Token (for PR integration)
   - Redis (for caching - or use Docker)

## 🎯 Step 1: Clone and Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd code-reviewer-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## 🔐 Step 2: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your API keys
nano .env  # or use your preferred editor
```

Required variables in `.env`:
```bash
ANTHROPIC_API_KEY=sk-ant-your-key-here
OPENAI_API_KEY=sk-your-key-here
```

Optional but recommended:
```bash
GITHUB_TOKEN=ghp_your-token-here
REDIS_HOST=localhost
DATABASE_URL=sqlite:///./code_reviews.db
```

## 🗄️ Step 3: Setup Database & Knowledge Base

```bash
# Setup database tables
python scripts/setup_db.py

# Seed knowledge base with best practices
python scripts/seed_knowledge_base.py
```

Expected output:
```
🌱 Seeding knowledge base...
📁 Data directory: /path/to/rag/data
✅ Knowledge base seeded successfully!
📊 Statistics:
   - best_practices: 15 documents
   - security_patterns: 8 documents
   - performance_tips: 12 documents
```

## 🚀 Step 4: Start the Services

### Option A: Quick Start (Local)

```bash
# Start Redis (if not using Docker)
redis-server

# In another terminal, start the API
uvicorn api.main:app --reload --port 8000

# In another terminal, start the UI (optional)
streamlit run ui/app.py
```

### Option B: Docker (Recommended)

```bash
# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f

# Check status
docker-compose ps
```

## ✅ Step 5: Verify Installation

### Test API Health
```bash
curl http://localhost:8000/api/v1/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "services": {
    "cache": "connected",
    "database": "connected",
    "llm": "ready"
  }
}
```

### Check Stats
```bash
curl http://localhost:8000/api/v1/stats
```

## 🎓 Step 6: Your First Review

### Simple File Review

Create a test file `test.py`:
```python
def divide(a, b):
    return a / b

user_input = input("Enter number: ")
result = divide(10, int(user_input))
print(result)
```

Review it via API:
```bash
curl -X POST "http://localhost:8000/api/v1/review/sync" \
  -H "Content-Type: application/json" \
  -d '{
    "files": [
      {
        "path": "test.py",
        "content": "def divide(a, b):\n    return a / b\n\nuser_input = input(\"Enter number: \")\nresult = divide(10, int(user_input))\nprint(result)",
        "language": "python"
      }
    ]
  }'
```

You'll receive a detailed review with:
- Bug detection (division by zero)
- Security issues (unsafe input handling)
- Best practice suggestions
- Overall quality score

## 🔧 Step 7: Configure for Your Needs

### Customize Agent Behavior

Edit `config/settings.py`:
```python
# Enable/disable specific agents
ENABLE_SECURITY = True
ENABLE_OPTIMIZER = True
ENABLE_DOCUMENTER = True

# Adjust confidence threshold
CONFIDENCE_THRESHOLD = 0.7  # Only show issues with >70% confidence

# Cost management
COST_LIMIT_PER_REVIEW = 1.0  # Max $1 per review
```

### Add Custom Best Practices

Create `rag/data/best_practices/mycompany.md`:
```markdown
# My Company Best Practices

## Naming Conventions
- Use snake_case for functions
- Use PascalCase for classes
- Prefix private methods with underscore

## Code Structure
- Keep files under 500 lines
- Maximum function length: 50 lines
```

Re-seed knowledge base:
```bash
python scripts/seed_knowledge_base.py
```

## 🔗 Step 8: GitHub Integration

### Setup GitHub Token

1. Go to GitHub Settings → Developer settings → Personal access tokens
2. Generate token with `repo` scope
3. Add to `.env`:
```bash
GITHUB_TOKEN=ghp_your_token_here
```

### Review a Pull Request

```bash
curl -X POST "http://localhost:8000/api/v1/review/github-pr" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_full_name": "your-username/your-repo",
    "pr_number": 123,
    "post_comments": true
  }'
```

The system will:
1. Fetch all changed files from the PR
2. Analyze them with all agents
3. Post a summary comment on the PR
4. Add inline comments on specific issues

### GitHub Actions Integration

Create `.github/workflows/ai-review.yml`:
```yaml
name: AI Code Review

on:
  pull_request:
    types: [opened, synchronize]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - name: AI Review
        run: |
          curl -X POST "${{ secrets.REVIEW_API_URL }}/api/v1/review/github-pr" \
            -H "Content-Type: application/json" \
            -d '{
              "repo_full_name": "${{ github.repository }}",
              "pr_number": ${{ github.event.pull_request.number }},
              "post_comments": true
            }'
```

## 📊 Step 9: Monitoring

### View Metrics
```bash
# System stats
curl http://localhost:8000/api/v1/stats

# Prometheus metrics
curl http://localhost:9090/metrics
```

### Check Logs
```bash
# Docker
docker-compose logs -f api

# Local
tail -f logs/app.log
```

## 🧪 Step 10: Test the System

```bash
# Run all tests
pytest

# Run specific test suite
pytest tests/unit/
pytest tests/integration/

# With coverage
pytest --cov=. --cov-report=html
open htmlcov/index.html
```

## 🎯 Common Use Cases

### 1. CI/CD Integration
Add to your build pipeline to automatically review code before merging.

### 2. Pre-commit Hook
```bash
# .git/hooks/pre-commit
#!/bin/bash
python review_local.py $(git diff --cached --name-only)
```

### 3. IDE Integration
Create a script to review current file:
```python
# review_current.py
import sys
from services.review_service import ReviewService

async def review_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
    
    service = ReviewService()
    result = await service.execute_review(
        review_id="ide-review",
        files=[CodeFile(filepath, content, "python", len(content), "hash")],
        options={}
    )
    
    print(result["executive_summary"])
    for issue in result["issues"]:
        print(f"Line {issue['line_start']}: {issue['title']}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(review_file(sys.argv[1]))
```

## 🐛 Troubleshooting

### API Key Errors
```
Error: ANTHROPIC_API_KEY not found
```
**Solution**: Check `.env` file has correct API keys

### Redis Connection Failed
```
Error: Could not connect to Redis
```
**Solution**: 
```bash
# Start Redis
redis-server
# Or use Docker
docker-compose up redis -d
```

### Knowledge Base Empty
```
Warning: No best practices found
```
**Solution**:
```bash
python scripts/seed_knowledge_base.py
```

### High API Costs
**Solution**: 
1. Enable caching in `.env`: `CACHE_TTL=3600`
2. Lower cost limit: `COST_LIMIT_PER_REVIEW=0.5`
3. Use selective agents for specific file types

## 🎓 Learning Path

### Beginner (Week 1)
1. ✅ Set up the system
2. ✅ Run basic reviews via API
3. ✅ Understand the output format
4. ✅ Customize confidence thresholds

### Intermediate (Week 2)
1. ✅ Add custom best practices
2. ✅ Integrate with GitHub
3. ✅ Set up CI/CD pipeline
4. ✅ Configure cost limits

### Advanced (Week 3+)
1. ✅ Customize agent prompts
2. ✅ Add new agent types
3. ✅ Implement custom tools
4. ✅ Scale with Kubernetes
5. ✅ Fine-tune for your domain

## 📚 Next Steps

1. **Read the full README.md** for detailed architecture
2. **Explore the API docs** at http://localhost:8000/docs
3. **Review example configurations** in `config/`
4. **Join the community** (add your community link)
5. **Contribute** by adding best practices or features

## 💡 Pro Tips

1. **Start Small**: Review individual files before full PRs
2. **Tune Confidence**: Adjust `CONFIDENCE_THRESHOLD` to reduce noise
3. **Use Caching**: Dramatically reduces costs for repeated reviews
4. **Monitor Costs**: Check `/api/v1/stats` regularly
5. **Customize Prompts**: Tailor agents to your coding standards
6. **Iterate**: The system improves as you add more best practices

## 🆘 Getting Help

- **Issues**: Create a GitHub issue
- **Docs**: Check `/docs` folder
- **Logs**: Check `logs/app.log`
- **Stats**: Monitor `/api/v1/stats` endpoint

---

**You're all set! Start reviewing code with AI! 🎉**