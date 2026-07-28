"""
minimal.py
Minimal resume template — clean, whitespace-focused, no decorative elements.
"""

MINIMAL_RESUME = {
    "plaintext": """\
{{ name }}
{{ title }}

{{ summary }}

Skills: {{ skills | join(', ') }}

{% for job in experience %}
{{ job.title }}, {{ job.company }} ({{ job.dates }})
{% for r in job.responsibilities %}{{ r }}
{% endfor %}{% for a in job.achievements %}{{ a }}
{% endfor %}{% for m in job.metrics %}{{ m }}
{% endfor %}{% endfor %}

{% if certifications %}
Certifications: {{ certifications | join(', ') }}
{% endif %}

{% if projects %}
Projects:
{% for project in projects %}{{ project }}
{% endfor %}{% endif %}

Education:
{% for edu in education %}{{ edu }}
{% endfor %}""",
    "markdown": """\
# {{ name }}

{{ title }}

{{ summary }}

**Skills:** {{ skills | join(', ') }}

{% for job in experience %}
## {{ job.title }}, {{ job.company }}

*{{ job.dates }}*

{% for r in job.responsibilities %}- {{ r }}
{% endfor %}{% for a in job.achievements %}- {{ a }}
{% endfor %}{% for m in job.metrics %}- {{ m }}
{% endfor %}{% endfor %}

{% if certifications %}
## Certifications

{{ certifications | join(', ') }}
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
