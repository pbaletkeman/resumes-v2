# Quick Reference of Models for Agent Output

## Regex/FormatDetector Models

| Model | Purpose |
| --- | --- |
| ParsedResume | Regex-parsed resume (flat list fields) |
| ParsedJobDescription | Regex-parsed job description |

## Agent Output Models

| Model | Purpose | Validators |
| --- | --- | --- |
| JDParsingOutput | Agent 1 output | `company_name`: default `""`; `company_signals`: coerces list to numbered dict |
| ExperienceEntry | Single role in work experience (title, company, dates, responsibilities, achievements, metrics) | |
| ResumeParsingOutput | Agent 2 output | `skills/projects/certifications/education`: `_coerce_str_list`; `experience`: `_coerce_experience_list` |
| GapAnalysisOutput | Agent 3 output | All `list[str]` fields: `_coerce_str_list`; `tone_guidance`: dict/list to comma-joined string |
| RewriteOutput | Agent 4 output | `experience`: `_coerce_experience_list` |
| ATSComplianceOutput | Agent 5 output | `ats_score`: Field(ge=0, le=100); all `list[str]` fields: `_coerce_str_list`; `final_resume`: dict to JSON string |
| TonePolishingOutput | Agent 6 output | |
| CoverLetterOutput | Agent 7 output | |

## Coercion Helpers

| Helper | Purpose |
| --- | --- |
| `_coerce_str_list` | Converts dicts, ints, None to `list[str]` — handles LLMs returning non-string items in list fields |
| `_coerce_experience_list` | Converts `list[str]` or `list[dict]` to `list[ExperienceEntry]` |

---

## Related

- [Previous: `logging-info.md`](logging-info.md)
- [Next: `skill-taxonomy.md`](skill-taxonomy.md)
- [Index: `docs/README.md`](README.md)
