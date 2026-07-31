"""
test_cover_letter.py
Test the Cover Letter Agent against a sample JD and resume.

Runs the full chain: JD Parsing -> Resume Parsing -> Gap Analysis ->
Resume Rewrite -> ATS Compliance -> Tone Polishing -> Cover Letter.

Prerequisites:
    - Ollama running on localhost:11434
    - Model pulled: ollama pull qwen2.5:7b-instruct

Usage:
    uv run python wip_testing/test_cover_letter.py
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from client.agents.ats_compliance import ATSComplianceAgent
from client.agents.cover_letter import CoverLetterAgent
from client.agents.gap_analysis import GapAnalysisAgent
from client.agents.jd_parsing import JDParsingAgent
from client.agents.resume_parsing import ResumeParsingAgent
from client.agents.resume_rewrite import ResumeRewriteAgent
from client.agents.tone_polishing import TonePolishingAgent
from client.ollama_client import OllamaClient

client = OllamaClient("qwen2.5:7b-instruct")

jd_agent = JDParsingAgent(client)
resume_agent = ResumeParsingAgent(client)
gap_agent = GapAnalysisAgent(client)
rewrite_agent = ResumeRewriteAgent(client)
ats_agent = ATSComplianceAgent(client)
tone_agent = TonePolishingAgent(client)
cover_agent = CoverLetterAgent(client)


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
    ats_result = await ats_agent.run({"rewritten_resume": rewritten})
    print(f"  ats_score:        {ats_result.ats_score}")
    print()

    # 6. Run tone polishing
    print("--- Running Tone Polishing ---")
    tone_result = await tone_agent.run(
        {"ats_optimized_resume": ats_result.final_resume}
    )
    print(f"  polished length:  {len(tone_result.polished_resume)} chars")
    print()

    # 7. Run cover letter generation
    print("--- Running Cover Letter Agent ---")
    cover_result = await cover_agent.run(
        {
            "parsed_job_description": parsed_jd,
            "parsed_resume": parsed_resume,
            "tailoring_strategy": strategy,
        }
    )

    word_count = len(cover_result.cover_letter.split())
    is_fallback = "[Your Name]" in cover_result.cover_letter
    print()
    print("=" * 60)
    print("=== Cover Letter Agent Output ===")
    print("=" * 60)
    print()
    if is_fallback:
        print("*** USING MINIMAL FALLBACK (LLM failed) ***")
    else:
        print("*** LLM SUCCESS ***")
    print()
    print("--- Cover Letter ---")
    print(cover_result.cover_letter)
    print()
    print(f"  word count: {word_count}")
    print()
    print("--- Raw JSON ---")
    print(json.dumps(cover_result.model_dump(), indent=2, default=str))


asyncio.run(main())
