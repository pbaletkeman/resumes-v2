"""
test_gap_analysis.py
Test the Gap Analysis Agent against a sample JD and resume.

Runs the JD Parsing Agent and Resume Parsing Agent first to produce
structured inputs, then feeds them into the Gap Analysis Agent.

Prerequisites:
    - Ollama running on localhost:11434
    - Model pulled: ollama pull qwen2.5:7b-instruct

Usage:
    uv run python wip_testing/test_gap_analysis.py
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from client.agents.gap_analysis import GapAnalysisAgent
from client.agents.jd_parsing import JDParsingAgent
from client.agents.resume_parsing import ResumeParsingAgent
from client.ollama_client import OllamaClient

client = OllamaClient("qwen2.5:7b-instruct")

jd_agent = JDParsingAgent(client)
resume_agent = ResumeParsingAgent(client)
gap_agent = GapAnalysisAgent(client)


async def main() -> None:
    # 1. Parse the job description
    with open("sample/jobs/3Pillar.txt", encoding="utf-8-sig") as f:
        jd_text = f.read()

    print("--- Parsing Job Description ---")
    parsed_jd = await jd_agent.run({"job_description": jd_text})
    print(f"  role_title:       {parsed_jd.role_title}")
    print(f"  required_skills:  {parsed_jd.required_skills[:5]}...")
    print(f"  keywords:         {parsed_jd.keywords[:5]}...")
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
    result = await gap_agent.run(
        {
            "parsed_job_description": parsed_jd,
            "parsed_resume": parsed_resume,
        }
    )

    print()
    print("=" * 60)
    print("=== Gap Analysis Agent Output ===")
    print("=" * 60)
    print()
    print(f"missing_skills:                  {result.missing_skills}")
    print(f"weak_skills:                     {result.weak_skills}")
    print(f"strong_matches:                  {result.strong_matches}")
    print(f"recommended_emphasis:            {result.recommended_emphasis}")
    print(f"keyword_strategy:                {result.keyword_strategy}")
    print(f"bullet_point_improvement_plan:   {result.bullet_point_improvement_plan}")
    print(f"tone_guidance:                   {result.tone_guidance}")
    print()
    print("--- Raw JSON ---")
    print(json.dumps(result.model_dump(), indent=2))


asyncio.run(main())
