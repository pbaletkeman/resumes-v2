"""
modern.py
Modern resume template — clean lines, bold section headers, compact layout.
"""

MODERN_RESUME = {
    "plaintext": """\
{{ name }}

{{ title }}

SUMMARY
{{ summary }}

SKILLS
{% for skill in skills %}- {{ skill }}
{% endfor %}

EXPERIENCE
{% for job in experience %}
{{ job.title }} at {{ job.company }} ({{ job.dates }})
{% for r in job.responsibilities %}- {{ r }}
{% endfor %}{% for a in job.achievements %}- {{ a }}
{% endfor %}{% for m in job.metrics %}- {{ m }}
{% endfor %}{% endfor %}

{% if certifications %}
CERTIFICATIONS
{% for cert in certifications %}- {{ cert }}
{% endfor %}
{% endif %}

{% if projects %}
PROJECTS
{% for project in projects %}- {{ project }}
{% endfor %}
{% endif %}

EDUCATION
{% for edu in education %}- {{ edu }}
{% endfor %}""",

    "markdown": """\
# {{ name }}

**{{ title }}**

## Summary

{{ summary }}

## Skills

{% for skill in skills %}- {{ skill }}
{% endfor %}

## Experience

{% for job in experience %}
### **{{ job.title }}** at **{{ job.company }}** ({{ job.dates }})

{% for r in job.responsibilities %}- {{ r }}
{% endfor %}{% for a in job.achievements %}- {{ a }}
{% endfor %}{% for m in job.metrics %}- {{ m }}
{% endfor %}{% endfor %}

{% if certifications %}
## Certifications

{% for cert in certifications %}- {{ cert }}
{% endfor %}
{% endif %}

{% if projects %}
## Projects

{% for project in projects %}- {{ project }}
{% endfor %}
{% endif %}

## Education

{% for edu in education %}- {{ edu }}
{% endfor %}""",
}
