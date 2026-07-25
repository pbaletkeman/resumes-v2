"""
test_real_files.py
Integration test that fetches a real job description and resume from GitHub,
then runs the full resume optimization pipeline.
"""

import asyncio
import urllib.error
import urllib.request

from client.ollama_client import OllamaClient
from client.resume_processor import ResumeProcessor


async def main() -> None:
    """Fetch remote documents and run the resume optimization pipeline.

    Downloads a sample job description and resume from the
    ``pbaletkeman/java-resumes`` GitHub repository, then processes
    them through ``ResumeProcessor.optimize_resume``.
    """
    jd_url = (
        "https://raw.githubusercontent.com/pbaletkeman/java-resumes/"
        "master/sample/PointClickCare-Software%20Engineer.txt"
    )
    resume_url = (
        "https://raw.githubusercontent.com/pbaletkeman/java-resumes/"
        "master/sample/resume.md"
    )

    try:
        print("Loading job description...")
        with urllib.request.urlopen(jd_url) as response:
            job_description = response.read().decode("utf-8")
    except urllib.error.URLError as e:
        print(f"Failed to load job description: {e}")
        return

    try:
        print("Loading resume...")
        with urllib.request.urlopen(resume_url) as response:
            resume = response.read().decode("utf-8")
    except urllib.error.URLError as e:
        print(f"Failed to load resume: {e}")
        return

    client = OllamaClient("qwen3.5")
    processor = ResumeProcessor(client)

    print("\n=== Processing Resume ===\n")
    result = await processor.optimize_resume(job_description, resume)

    print("Gap Analysis:")
    print(result["gap_analysis"][:500])
    print("\n...")

    print("\n\nRewritten Resume:")
    print(result["rewritten_resume"][:500])
    print("\n...")

    print("\n\nATS Compliance:")
    print(result["ats_compliance"][:500])


asyncio.run(main())
