# Quick Reference of Models for Agent Output

## Regex/FormatDetector Models

| Model | Purpose |
| --- | --- |
| ParsedResume | Regex-parsed resume (flat list fields) |
| ParsedJobDescription | Regex-parsed job description |
| JDParsingOutput | Agent 1 output |

## Agent Output Models

| Model | Purpose |
| --- | --- |
| ExperienceEntry | Single role in work experience (title, company, dates, responsibilities, achievements, metrics) |
| ResumeParsingOutput | Agent 2 output |
| GapAnalysisOutput | Agent 3 output |
| RewriteOutput | Agent 4 output |
| ATSComplianceOutput | Agent 5 output (with Field(ge=0, le=100) on ats_score) |
| TonePolishingOutput | Agent 6 output |
| CoverLetterOutput | Agent 7 output |
