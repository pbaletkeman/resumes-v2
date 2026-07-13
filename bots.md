# 🧩 Full Agent Pipeline (7 agents)

## 1. JD Parsing Agent

**Extracts**:

- Required skills
- Responsibilities
- Keywords
- Seniority signals
- Domain‑specific terminology

## 2. Resume Parsing Agent

**Extracts**:

- Experience
- Achievements
- Skills
- Quantifiable metrics
- Role‑specific accomplishments

## 3. Gap Analysis Agent

**Compares JD vs resume and produces**:

- Missing skills
- Weakly represented areas
- Recommended emphasis
- Keyword strategy
- Rewrite plan

## 4. Rewrite Agent

**Generates**:

- Updated bullet points
- Quantified achievements
- Keyword‑aligned phrasing
- Updated summary + skills section

This is the heavy generative step.

## 5. ATS Compliance Agent

**Checks**:

- Keyword coverage
- Action verbs
- Formatting consistency
- Section structure
- Readability score
- Overuse of soft skills
- Missing hard skills
- ATS‑unfriendly elements (tables, images, odd characters)

**Outputs**:

- Compliance score
- Fix list
- Auto‑applied corrections

## 6. Tone Polishing Agent

**Improves**:

- Professional tone
- Confidence level
- Clarity
- Flow
- Narrative cohesion
- Role‑appropriate voice (technical, managerial, creative)

**Outputs**:

- Final polished resume

## 7. Cover Letter Agent

**This agent takes**:

- Parsed job description
- Parsed resume
- Gap analysis strategy
- Optional user inputs (tone, length, company name, etc.)

**And produces a tailored cover letter that includes**:

- A strong opening hook
- A narrative that aligns your experience with the job
- A highlight of your most relevant achievements
- A confident closing paragraph
- ATS‑friendly keywords woven naturally
- Tone matched to the role (technical, managerial, creative)
