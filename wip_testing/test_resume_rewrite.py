"""
test_resume_rewrite.py
Test the Resume Rewrite Agent against a sample JD and resume.

Runs the full chain: JD Parsing -> Resume Parsing -> Gap Analysis ->
Resume Rewrite.

Prerequisites:
    - Ollama running on localhost:11434
    - Model pulled: ollama pull qwen2.5:7b-instruct

Usage:
    uv run python wip_testing/test_resume_rewrite.py
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from client.agents.gap_analysis import GapAnalysisAgent
from client.agents.jd_parsing import JDParsingAgent
from client.agents.resume_parsing import ResumeParsingAgent
from client.agents.resume_rewrite import ResumeRewriteAgent
from client.ollama_client import OllamaClient

client = OllamaClient("qwen2.5:7b-instruct")

jd_agent = JDParsingAgent(client)
resume_agent = ResumeParsingAgent(client)
gap_agent = GapAnalysisAgent(client)
rewrite_agent = ResumeRewriteAgent(client)


async def main() -> None:
    # 1. Parse the job description
    with open("sample/jobs/3Pillar.txt", encoding="utf-8-sig") as f:
        jd_text = f.read()

    print("--- Parsing Job Description ---")
    parsed_jd = await jd_agent.run({"job_description": jd_text})
    print(f"  role_title:       {parsed_jd.role_title}")
    print(f"  required_skills:  {parsed_jd.required_skills[:5]}...")
    print()

    # 2. Parse the resume
    with open("sample/resume/Peter-Letkeman-Resume.txt", encoding="utf-8-sig") as f:
        resume_text = f.read()

    print("--- Parsing Resume ---")
    parsed_resume = await resume_agent.run({"resume": resume_text})
    print(f"  skills:           {parsed_resume.skills[:5]}...")
    print(f"  experience count: {len(parsed_resume.experience)}")
    print(f"  certifications:   {parsed_resume.certifications}")
    print()

    # 3. Run gap analysis
    print("--- Running Gap Analysis ---")
    strategy = await gap_agent.run(
        {
            "parsed_job_description": parsed_jd,
            "parsed_resume": parsed_resume,
        }
    )
    print(f"  missing_skills:   {strategy.missing_skills[:3]}...")
    print(f"  strong_matches:   {strategy.strong_matches[:3]}...")
    print()

    # 4. Run resume rewrite
    print("--- Running Resume Rewrite ---")
    result = await rewrite_agent.run(
        {
            "parsed_resume": parsed_resume,
            "tailoring_strategy": strategy,
        }
    )

    print()
    print("=" * 60)
    print("=== Resume Rewrite Agent Output ===")
    print("=" * 60)
    print()
    print(f"summary:            {result.summary[:100]}...")
    print(f"skills:             {result.skills[:5]}...")
    print(f"experience count:   {len(result.experience)}")
    print(f"projects:           {result.projects[:3]}...")
    print(f"certifications:     {result.certifications}")
    print(f"education:          {result.education}")
    print()

    print("--- Experience Details ---")
    for i, exp in enumerate(result.experience):
        print(f"  [{i}] title:            {exp.title}")
        print(f"      company:          {exp.company}")
        print(f"      dates:            {exp.dates}")
        print(f"      responsibilities: {exp.responsibilities[:2]}...")
        print(f"      achievements:     {exp.achievements[:2]}...")
        print(f"      metrics:          {exp.metrics}")
        print()

    print("--- Raw JSON ---")
    print(json.dumps(result.model_dump(), indent=2, default=str))


asyncio.run(main())
