# tools/static_analyzers.py
"""
Static analysis tools integration
"""
import subprocess
import json
from typing import List, Dict, Any
from core.state import CodeFile, StaticAnalysisResult
import structlog

logger = structlog.get_logger()


async def run_static_analysis(code_file: CodeFile) -> StaticAnalysisResult:
    """Run appropriate static analyzer based on language"""
    
    if code_file.language == "python":
        return await run_ruff(code_file)
    elif code_file.language in ["javascript", "typescript"]:
        return await run_eslint(code_file)
    else:
        return StaticAnalysisResult(
            tool_name="none",
            issues=[],
            execution_time=0,
            success=True
        )


async def run_ruff(code_file: CodeFile) -> StaticAnalysisResult:
    """Run Ruff linter on Python code"""
    import time
    start = time.time()
    
    try:
        # Write code to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code_file.content)
            temp_path = f.name
        
        # Run ruff
        result = subprocess.run(
            ['ruff', 'check', temp_path, '--output-format', 'json'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Parse output
        issues = []
        if result.stdout:
            data = json.loads(result.stdout)
            for item in data:
                issues.append({
                    "line": item.get("location", {}).get("row", 0),
                    "message": item.get("message", ""),
                    "code": item.get("code", ""),
                    "severity": "minor"
                })
        
        return StaticAnalysisResult(
            tool_name="ruff",
            issues=issues,
            execution_time=time.time() - start,
            success=True
        )
        
    except Exception as e:
        logger.error("ruff_failed", error=str(e))
        return StaticAnalysisResult(
            tool_name="ruff",
            issues=[],
            execution_time=time.time() - start,
            success=False,
            error=str(e)
        )


async def run_eslint(code_file: CodeFile) -> StaticAnalysisResult:
    """Run ESLint on JavaScript/TypeScript"""
    import time
    start = time.time()
    
    try:
        import tempfile
        suffix = '.js' if code_file.language == 'javascript' else '.ts'
        with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False) as f:
            f.write(code_file.content)
            temp_path = f.name
        
        result = subprocess.run(
            ['eslint', temp_path, '-f', 'json'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        issues = []
        if result.stdout:
            data = json.loads(result.stdout)
            for file_result in data:
                for message in file_result.get('messages', []):
                    issues.append({
                        "line": message.get("line", 0),
                        "message": message.get("message", ""),
                        "rule": message.get("ruleId", ""),
                        "severity": "major" if message.get("severity") == 2 else "minor"
                    })
        
        return StaticAnalysisResult(
            tool_name="eslint",
            issues=issues,
            execution_time=time.time() - start,
            success=True
        )
        
    except Exception as e:
        logger.error("eslint_failed", error=str(e))
        return StaticAnalysisResult(
            tool_name="eslint",
            issues=[],
            execution_time=time.time() - start,
            success=False,
            error=str(e)
        )


# ============================================================



# ============================================================



# ============================================================


# ============================================================
