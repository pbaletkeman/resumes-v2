"""
test_real_files.py
Test with actual GitHub job description and resume.
"""

import asyncio
import os
import urllib.request

from client.ollama_client import OllamaClient
from client.resume_processor import ResumeProcessor


async def main() -> None:
    """Test resume processing with real job description and resume."""

    # Load real files from GitHub
    jd_url = "https://raw.githubusercontent.com/pbaletkeman/java-resumes/master/sample/PointClickCare-Software%20Engineer.txt"
    resume_url = "https://raw.githubusercontent.com/pbaletkeman/java-resumes/master/sample/resume.md"

    print("Loading job description...")
    with urllib.request.urlopen(jd_url) as response:
        job_description = response.read().decode('utf-8')

    print("Loading resume...")
    with urllib.request.urlopen(resume_url) as response:
        resume = response.read().decode('utf-8')

    # Initialize client
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
