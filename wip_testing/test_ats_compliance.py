"""
test_ats_compliance.py
Test the ATS Compliance Agent against a sample JD and resume.

Runs the full chain: JD Parsing -> Resume Parsing -> Gap Analysis ->
Resume Rewrite -> ATS Compliance.

Prerequisites:
    - Ollama running on localhost:11434
    - Model pulled: ollama pull qwen2.5:7b-instruct

Usage:
    uv run python wip_testing/test_ats_compliance.py
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from client.agents.ats_compliance import ATSComplianceAgent
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
ats_agent = ATSComplianceAgent(client)


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
    print()

    # 4. Run resume rewrite
    print("--- Running Resume Rewrite ---")
    rewritten = await rewrite_agent.run(
        {
            "parsed_resume": parsed_resume,
            "tailoring_strategy": strategy,
        }
    )
    print(f"  experience count: {len(rewritten.experience)}")
    print(f"  certifications:   {rewritten.certifications}")
    print()

    # 5. Run ATS compliance
    print("--- Running ATS Compliance ---")
    result = await ats_agent.run({"rewritten_resume": rewritten})

    print()
    print("=" * 60)
    print("=== ATS Compliance Agent Output ===")
    print("=" * 60)
    print()
    print(f"ats_score:             {result.ats_score}")
    print(f"missing_keywords:      {result.missing_keywords}")
    print(f"formatting_issues:     {result.formatting_issues}")
    print(f"clarity_issues:        {result.clarity_issues}")
    print(f"recommended_fixes:     {result.recommended_fixes}")
    print(f"auto_fixes_applied:    {result.auto_fixes_applied}")
    print()
    print("--- Final Resume (first 500 chars) ---")
    print(result.final_resume[:500])
    print()
    print("--- Raw JSON ---")
    print(json.dumps(result.model_dump(), indent=2, default=str))


asyncio.run(main())
