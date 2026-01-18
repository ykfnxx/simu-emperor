#!/usr/bin/env python3
"""Fix apostrophe issues in event_templates.py"""

import re

# Read the file
with open('events/event_templates.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the problematic lines
content = content.replace(
    "'This province's key officials are replaced, increasing loyalty'",
    '"This province\'s key officials are replaced, increasing loyalty"'
)

content = content.replace(
    "'This province's border experiences conflict, increasing expenses and decreasing stability'",
    '"This province\'s border experiences conflict, increasing expenses and decreasing stability"'
)

# Write back
with open('events/event_templates.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed apostrophe issues in event_templates.py")
