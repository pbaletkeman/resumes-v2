"""
test_resume_parsing.py
Test the Resume Parsing Agent against a sample resume.

Usage:
    uv run python wip_testing/test_resume_parsing.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from client.agents.resume_parsing import ResumeParsingAgent
from client.ollama_client import OllamaClient

client = OllamaClient("qwen2.5:7b-instruct")
agent = ResumeParsingAgent(client)

with open("sample/resume/Peter-Letkeman-Resume.txt", encoding="utf-8-sig") as f:
    resume = f.read()

result = asyncio.run(agent.run({"resume": resume}))

print("=== Resume Parsing Agent Output ===")
print(f"summary:         {result.summary}")
print(f"skills:          {result.skills}")
print(f"projects:        {result.projects}")
print(f"certifications:  {result.certifications}")
print(f"education:       {result.education}")
print()
print("--- Experience ---")
for i, exp in enumerate(result.experience):
    print(f"  [{i}] title:           {exp.title}")
    print(f"      company:         {exp.company}")
    print(f"      dates:           {exp.dates}")
    print(f"      responsibilities: {exp.responsibilities}")
    print(f"      achievements:    {exp.achievements}")
    print(f"      metrics:         {exp.metrics}")
    print()
