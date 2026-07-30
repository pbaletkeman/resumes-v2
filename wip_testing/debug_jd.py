"""
debug_jd.py
Test the JD Parsing Agent against a sample job description.

Usage:
    uv run python wip_testing/debug_jd.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from client.agents.jd_parsing import JDParsingAgent
from client.ollama_client import OllamaClient

client = OllamaClient("qwen2.5:7b-instruct")
agent = JDParsingAgent(client)

with open("sample/jobs/3Pillar.txt", encoding="utf-8-sig") as f:
    jd = f.read()

result = asyncio.run(agent.run({"job_description": jd}))

print("=== JD Parsing Agent Output ===")
print(f"role_title:        {result.role_title}")
print(f"seniority_level:   {result.seniority_level}")
print(f"required_skills:   {result.required_skills}")
print(f"preferred_skills:  {result.preferred_skills}")
print(f"responsibilities:  {result.responsibilities}")
print(f"keywords:          {result.keywords}")
print(f"industry_terms:    {result.industry_terms}")
print(f"company_signals:   {result.company_signals}")
