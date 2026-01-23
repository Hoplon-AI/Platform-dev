#!/usr/bin/env python3
"""Script to find custom field IDs in Jira."""

import os
from jira import JIRA

JIRA_SERVER = os.getenv('JIRA_SERVER', 'https://equirisk.atlassian.net')
JIRA_EMAIL = os.getenv('JIRA_EMAIL', 'rcastro.dev@gmail.com')
JIRA_API_TOKEN = os.getenv('JIRA_API_TOKEN')
JIRA_PROJECT_KEY = os.getenv('JIRA_PROJECT_KEY', 'KAN')

if not JIRA_API_TOKEN:
    print("Error: JIRA_API_TOKEN not set")
    exit(1)

jira = JIRA(server=JIRA_SERVER, basic_auth=(JIRA_EMAIL, JIRA_API_TOKEN))

# Get all fields
print("Finding custom field IDs...\n")
fields = jira.fields()

# Find Epic Link and Story Points fields
epic_link_fields = []
story_points_fields = []

for field in fields:
    field_name = field.get('name', '')
    field_id = field.get('id', '')
    
    if 'epic' in field_name.lower() and 'link' in field_name.lower():
        epic_link_fields.append((field_id, field_name))
    if 'story point' in field_name.lower() or 'storypoint' in field_name.lower():
        story_points_fields.append((field_id, field_name))

print("Epic Link fields:")
for field_id, field_name in epic_link_fields:
    print(f"  {field_id}: {field_name}")

print("\nStory Points fields:")
for field_id, field_name in story_points_fields:
    print(f"  {field_id}: {field_name}")

# Also check existing Epic to see its fields
try:
    epic = jira.issue('KAN-9')
    print(f"\nExisting Epic KAN-9 fields:")
    for key, value in epic.raw['fields'].items():
        if 'epic' in key.lower() or 'story' in key.lower() or 'point' in key.lower():
            print(f"  {key}: {value}")
except Exception as e:
    print(f"\nCould not check Epic KAN-9: {e}")
