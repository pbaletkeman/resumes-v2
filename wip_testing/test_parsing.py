"""
uv run python wip_testing/test_parsing.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from client.format_detector import FormatDetector
from client.ollama_client import OllamaClient

client = OllamaClient("qwen2.5:7b-instruct")

fd_regex = FormatDetector()  # no LLM, regex only
fd_llm = FormatDetector(client=client)  # regex + LLM fallback

with open("sample/resume/Peter-Letkeman-Resume.txt", encoding="utf-8-sig") as f:
    resume = f.read()

print("=== REGEX only, no LLM ===")
result = asyncio.run(fd_regex.parse_resume(resume))
print("Name:", result.name)
print("Skills:", result.skills)
print("Experience entries:", len(result.experience))

print("\n=== REGEX + LLM fallback ===")
result = asyncio.run(fd_llm.parse_resume(resume))
print("Name:", result.name)
print("Skills:", result.skills)
print("Experience entries:", len(result.experience))

with open("sample/jobs/3Pillar.txt", encoding="utf-8-sig") as f:
    jd = f.read()

print("\n=== JD: REGEX only ===")
result = asyncio.run(fd_regex.parse_job_description(jd))
print("Title:", result.title)
print("Requirements:", result.requirements)
print("Nice to have:", result.nice_to_have)

print("\n=== JD: REGEX + LLM fallback ===")
result = asyncio.run(fd_llm.parse_job_description(jd))
print("Title:", result.title)
print("Requirements:", result.requirements)
print("Nice to have:", result.nice_to_have)
