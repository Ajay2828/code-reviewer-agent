# 🤖 AI Code Review Agent System

A production-ready, multi-agent code review system powered by Claude Sonnet 4 and GPT-4, featuring advanced techniques like RAG, caching, streaming, and GitHub integration.

## 🌟 Features

### Core Capabilities
- ✅ **Multi-Agent Architecture**: 4 specialized agents (Analyzer, Security, Optimizer, Documenter)
- ✅ **Chain-of-Thought Reasoning**: Agents explain their analysis step-by-step
- ✅ **Self-Reflection**: Agents validate their own findings to reduce false positives
- ✅ **RAG System**: Retrieves best practices from knowledge base
- ✅ **Smart Caching**: Redis-backed caching prevents redundant analysis
- ✅ **Cost Optimization**: Tracks API usage and respects budget limits
- ✅ **Streaming Support**: Real-time progress updates

### Integrations
- ✅ **GitHub/GitLab**: Automatic PR reviews with inline comments
- ✅ **Static Analysis**: Integrates Ruff, Pylint, ESLint, Semgrep
- ✅ **CI/CD Ready**: Webhook support for automated reviews

### Production Features
- ✅ **Structured Outputs**: Consistent JSON responses
- ✅ **Error Handling**: Automatic fallback between LLMs
- ✅ **Metrics**: Prometheus-compatible monitoring
- ✅ **Docker Support**: Full containerization
- ✅ **REST API**: FastAPI-based API server
- ✅ **Web UI**: Streamlit interface for interactive use

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Code Review Request                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   LangGraph Orchestrator                     │
├─────────────────────────────────────────────────────────────┤
│  1. Static Analysis (Ruff, Pylint, ESLint)                  │
│  2. RAG Query (Best Practices Retrieval)                    │
│  3. Multi-Agent Analysis (Parallel)                         │
│     ├── Analyzer Agent (Bugs, Logic Errors)                 │
│     ├── Security Agent (Vulnerabilities)                    │
│     ├── Optimizer Agent (Performance)                       │
│     └── Documenter Agent (Documentation Quality)            │
│  4. Consolidation (Deduplication, Prioritization)           │
│  5. Summary Generation                                       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Review Output                             │
│  - Executive Summary                                         │
│  - Consolidated Issues (sorted by severity)                 │
│  - Overall Quality Score (0-100)                            │
│  - Recommendation (approve/request_changes/reject)          │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose (optional)
- Anthropic API key
- OpenAI API key

### Installation

1. **Clone the repository**
```bash
git clone <repo-url>
cd code-reviewer-agent
```

2. **Set up environment**
```bash
cp .env.example .env
# Edit .env with your API keys
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Initialize knowledge base**
```bash
python scripts/seed_knowledge_base.py
```

5. **Start services**

**Option A: Docker (Recommended)**
```bash
docker-compose up -d
```

**Option B: Local Development**
```bash
# Terminal 1: Start Redis
redis-server

# Terminal 2: Start API
uvicorn api.main:app --reload

# Terminal 3: Start UI (optional)
streamlit run ui/app.py
```

### Access Points
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Streamlit UI: http://localhost:8501
- Metrics: http://localhost:9090

## 📚 Usage Examples

### 1. API: Review Code Directly

```bash
curl -X POST "http://localhost:8000/api/v1/review/sync" \
  -H "Content-Type: application/json" \
  -d '{
    "files": [
      {
        "path": "app.py",
        "content": "def calculate(x, y):\n    return x / y",
        "language": "python"
      }
    ],
    "options": {
      "enable_security": true,
      "enable_performance": true
    }
  }'
```

### 2. API: Review GitHub PR

```bash
curl -X POST "http://localhost:8000/api/v1/review/github-pr" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_full_name": "owner/repo",
    "pr_number": 123,
    "post_comments": true
  }'
```

### 3. Python SDK

```python
import asyncio
from services.review_service import ReviewService
from core.state import CodeFile

async def review_code():
    service = ReviewService()
    
    files = [
        CodeFile(
            path="example.py",
            content="def add(a, b): return a + b",
            language="python",
            size=30,
            hash="abc123"
        )
    ]
    
    result = await service.execute_review(
        review_id="test-001",
        files=files,
        options={}
    )
    
    print(result["executive_summary"])
    print(f"Score: {result['overall_score']}/100")
    print(f"Issues found: {result['statistics']['total_issues']}")

asyncio.run(review_code())
```

### 4. GitHub Actions Integration

```yaml
# .github/workflows/code-review.yml
name: AI Code Review

on:
  pull_request:
    types: [opened, synchronize]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Run AI Code Review
        run: |
          curl -X POST "${{ secrets.REVIEW_API_URL }}/api/v1/review/github-pr" \
            -H "Content-Type: application/json" \
            -d '{
              "repo_full_name": "${{ github.repository }}",
              "pr_number": ${{ github.event.pull_request.number }},
              "post_comments": true
            }'
```

## 🎯 Advanced Concepts Explained

### 1. Multi-Agent System
Each agent specializes in a specific aspect:
- **Analyzer**: Detects bugs, logic errors, edge cases
- **Security**: Finds vulnerabilities (SQL injection, XSS, etc.)
- **Optimizer**: Suggests performance improvements
- **Documenter**: Reviews code documentation quality

Agents run in parallel for speed, then results are consolidated.

### 2. Chain-of-Thought Reasoning
Agents are prompted to think step-by-step:
```
1. Understand the code's purpose
2. Identify control flow
3. Check for common patterns
4. Assess edge cases
5. Generate findings
```

This improves accuracy and provides transparent reasoning.

### 3. Self-Reflection
After initial analysis, agents review their own findings:
- Identify false positives
- Adjust confidence scores
- Add missing issues

This reduces noise and improves precision.

### 4. RAG (Retrieval Augmented Generation)
The system maintains a knowledge base of:
- Language-specific best practices
- Security patterns
- Performance optimization techniques
- Common bug patterns

Before reviewing, relevant practices are retrieved and provided to agents.

### 5. Smart Caching
Results are cached using: `hash(file_path + content_hash + agent_name)`

Benefits:
- Avoid re-analyzing unchanged code
- Reduce API costs
- Speed up repeated reviews

### 6. Cost Management
- Tracks tokens and cost per request
- Enforces per-review budget limits
- Uses cheaper models when appropriate
- Caches aggressively

## 🔧 Configuration

### Agent Behavior

```python
# config/settings.py

# Enable/disable agents
ENABLE_SECURITY_AGENT = True
ENABLE_OPTIMIZER_AGENT = True

# Self-reflection
ENABLE_SELF_REFLECTION = True
CONFIDENCE_THRESHOLD = 0.7  # Only show issues above this confidence

# Cost limits
COST_LIMIT_PER_REVIEW = 1.0  # USD
```

### Custom Prompts

Edit `config/prompts.py` to customize agent behavior:
```python
ANALYZER_PROMPT = """
Your custom instructions here...
Focus on: {specific_areas}
"""
```

### Adding Best Practices

Add markdown files to `rag/data/`:
```
rag/data/
  best_practices/
    python.md           # Python best practices
    javascript.md       # JS best practices
  security_patterns/
    sql_injection.md    # How to prevent SQL injection
  performance_tips/
    database.md         # DB optimization tips
```

Then run: `python scripts/seed_knowledge_base.py`

## 🔐 Security Considerations

1. **API Keys**: Never commit `.env` to git
2. **Webhook Secrets**: Use strong secrets for webhooks
3. **Rate Limiting**: Implement rate limits in production
4. **Input Validation**: All inputs are validated
5. **Sandboxing**: Static analysis runs in isolated environment

## 📊 Monitoring

### Prometheus Metrics
```python
# Available metrics
code_review_requests_total
code_review_duration_seconds
agent_execution_duration_seconds
llm_api_cost_usd
cache_hit_rate
```

### Logging
Structured JSON logs with:
- Request tracing
- Performance metrics
- Error details
- Cost tracking

## 🧪 Testing

```bash
# Run all tests
pytest

# Unit tests only
pytest tests/unit/

# Integration tests
pytest tests/integration/

# E2E tests
pytest tests/e2e/

# With coverage
pytest --cov=. --cov-report=html
```

## 🚢 Deployment

### Production Checklist
- [ ] Set strong passwords in `.env`
- [ ] Configure webhook secrets
- [ ] Set up SSL/TLS certificates
- [ ] Configure rate limiting
- [ ] Set up monitoring and alerts
- [ ] Configure backup for PostgreSQL
- [ ] Set cost limits
- [ ] Enable caching
- [ ] Configure log aggregation

### Kubernetes Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: code-reviewer-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: code-reviewer-api
  template:
    metadata:
      labels:
        app: code-reviewer-api
    spec:
      containers:
      - name: api
        image: code-reviewer:latest
        env:
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: api-keys
              key: anthropic
        ports:
        - containerPort: 8000
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📝 License

MIT License - see LICENSE file

## 🙏 Acknowledgments

- Anthropic Claude for powerful code analysis
- OpenAI GPT-4 for fallback support
- LangChain/LangGraph for orchestration
- FastAPI for the web framework

## 📧 Support

For issues, questions, or suggestions:
- Create a GitHub issue
- Email: support@example.com
- Docs: https://docs.example.com

---

**Built with ❤️ using Claude Sonnet 4 and modern AI agent patterns**