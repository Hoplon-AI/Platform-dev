#!/usr/bin/env python3
"""
Test script to create a single Jira ticket (first Epic) to verify connection.
"""

import os
import sys
from pathlib import Path

try:
    from jira import JIRA
except ImportError:
    print("Error: jira package not installed. Run: pip install jira")
    sys.exit(1)

# Configuration from environment
JIRA_SERVER = os.getenv('JIRA_SERVER', 'https://equirisk.atlassian.net')
JIRA_EMAIL = os.getenv('JIRA_EMAIL', 'rcastro.dev@gmail.com')
JIRA_API_TOKEN = os.getenv('JIRA_API_TOKEN')
JIRA_PROJECT_KEY = os.getenv('JIRA_PROJECT_KEY', 'KAN')

if not JIRA_API_TOKEN:
    print("Error: JIRA_API_TOKEN environment variable not set")
    sys.exit(1)

def main():
    print("=" * 60)
    print("Jira Connection Test - Creating First Epic")
    print("=" * 60)
    
    try:
        # Connect to Jira
        print(f"\nConnecting to {JIRA_SERVER}...")
        jira = JIRA(
            server=JIRA_SERVER,
            basic_auth=(JIRA_EMAIL, JIRA_API_TOKEN)
        )
        
        # Test connection
        user = jira.current_user()
        print(f"✓ Connected as {user}")
        
        # Create first Epic
        print("\nCreating first Epic: 'Frontend Infrastructure & UPRN Mapping Service'...")
        
        issue_dict = {
            'project': {'key': JIRA_PROJECT_KEY},
            'summary': 'Frontend Infrastructure & UPRN Mapping Service',
            'description': 'Set up React frontend application, base components, and implement UPRN mapping service using OS DataHub API',
            'issuetype': {'name': 'Epic'},
            'priority': {'name': 'Highest'},
        }
        
        new_epic = jira.create_issue(fields=issue_dict)
        
        # Try to set Epic Name (custom field)
        try:
            # Common Epic Name field IDs (try different ones)
            epic_name_fields = ['customfield_10011', 'customfield_10014']
            for field_id in epic_name_fields:
                try:
                    new_epic.update(fields={field_id: 'Frontend Infrastructure & UPRN Mapping Service'})
                    print(f"  ✓ Set Epic Name using field {field_id}")
                    break
                except:
                    continue
        except Exception as e:
            print(f"  ⚠ Could not set Epic Name (may need manual update): {e}")
        
        print(f"\n✓ Successfully created Epic!")
        print(f"  Ticket Key: {new_epic.key}")
        print(f"  Summary: {new_epic.fields.summary}")
        print(f"  URL: {JIRA_SERVER}/browse/{new_epic.key}")
        print(f"\n  View in board: {JIRA_SERVER}/jira/software/projects/{JIRA_PROJECT_KEY}/boards/1")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
