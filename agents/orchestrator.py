# Orchestrator to run agents
from .analyzer_agent import AnalyzerAgent

def orchestrate(code):
    analyzer = AnalyzerAgent()
    return analyzer.run(code)
