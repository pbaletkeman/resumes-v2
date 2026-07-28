"""
classic.py
Classic resume template — traditional format with underlined section headers.
"""

CLASSIC_RESUME = {
    "plaintext": """\
{{ name }}
{{ title }}

--------------------------------------------------------------------------------

Professional Summary
{{ summary }}

--------------------------------------------------------------------------------

Core Competencies
{% for skill in skills %}  * {{ skill }}
{% endfor %}

--------------------------------------------------------------------------------

Professional Experience
{% for job in experience %}
{{ job.title }}
{{ job.company }} | {{ job.dates }}

Responsibilities:
{% for r in job.responsibilities %}  * {{ r }}
{% endfor %}
{% if job.achievements %}
Achievements:
{% for a in job.achievements %}  * {{ a }}
{% endfor %}{% endif %}
{% if job.metrics %}
Metrics:
{% for m in job.metrics %}  * {{ m }}
{% endfor %}{% endif %}{% endfor %}

--------------------------------------------------------------------------------
{% if certifications %}
Certifications
{% for cert in certifications %}  * {{ cert }}
{% endfor %}

--------------------------------------------------------------------------------
{% endif %}
{% if projects %}
Projects
{% for project in projects %}  * {{ project }}
{% endfor %}

--------------------------------------------------------------------------------
{% endif %}
Education
{% for edu in education %}  * {{ edu }}
{% endfor %}""",

    "markdown": """\
# {{ name }}

**{{ title }}**

---

## Professional Summary

{{ summary }}

---

## Core Competencies

{% for skill in skills %}* {{ skill }}
{% endfor %}

---

## Professional Experience

{% for job in experience %}
### {{ job.title }}

**{{ job.company }}** | {{ job.dates }}

**Responsibilities:**
{% for r in job.responsibilities %}* {{ r }}
{% endfor %}
{% if job.achievements %}
**Achievements:**
{% for a in job.achievements %}* {{ a }}
{% endfor %}{% endif %}
{% if job.metrics %}
**Metrics:**
{% for m in job.metrics %}* {{ m }}
{% endfor %}{% endif %}
{% endfor %}

---
{% if certifications %}
## Certifications

{% for cert in certifications %}* {{ cert }}
{% endfor %}

---
{% endif %}
{% if projects %}
## Projects

{% for project in projects %}* {{ project }}
{% endfor %}

---
{% endif %}
## Education

{% for edu in education %}* {{ edu }}
{% endfor %}""",
}
