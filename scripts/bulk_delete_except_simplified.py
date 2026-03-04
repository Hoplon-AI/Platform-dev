#!/usr/bin/env python3
"""
Script to bulk delete all newly created Jira tickets except the 20 simplified tickets.
Keeps: KAN-9, KAN-402-406 (Epics), KAN-442-448 (Stories), KAN-449-455 (Tasks)
"""

import os
import sys
from jira import JIRA

JIRA_SERVER = os.getenv('JIRA_SERVER', 'https://equirisk.atlassian.net')
JIRA_EMAIL = os.getenv('JIRA_EMAIL')
JIRA_API_TOKEN = os.getenv('JIRA_API_TOKEN')
JIRA_PROJECT_KEY = os.getenv('JIRA_PROJECT_KEY', 'KAN')

if not JIRA_API_TOKEN:
    print("Error: JIRA_API_TOKEN not set")
    sys.exit(1)

if not JIRA_EMAIL:
    print("Error: JIRA_EMAIL not set")
    sys.exit(1)

# Tickets to keep (the 20 simplified ones)
KEEP_TICKETS = {
    # Epics
    'KAN-9', 'KAN-402', 'KAN-403', 'KAN-404', 'KAN-405', 'KAN-406',
    # Stories
    'KAN-442', 'KAN-443', 'KAN-444', 'KAN-445', 'KAN-446', 'KAN-447', 'KAN-448',
    # Tasks
    'KAN-449', 'KAN-450', 'KAN-451', 'KAN-452', 'KAN-453', 'KAN-454', 'KAN-455',
}

def main():
    print("=" * 60)
    print("Bulk Delete Jira Tickets (Keep Simplified Set)")
    print("=" * 60)
    
    try:
        jira = JIRA(server=JIRA_SERVER, basic_auth=(JIRA_EMAIL, JIRA_API_TOKEN))
        user = jira.current_user()
        print(f"✓ Connected as {user}\n")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        sys.exit(1)
    
    # Get all issues created today (or recently)
    print("Finding issues to delete...")
    # Search for issues created today or in the last few days
    issues = jira.search_issues('project=KAN AND created >= "2025-01-27" ORDER BY key', maxResults=1000)
    
    # Filter out the tickets we want to keep
    issues_to_delete = [i for i in issues if i.key not in KEEP_TICKETS]
    
    print(f"Found {len(issues)} total issues created recently")
    print(f"Keeping {len(KEEP_TICKETS)} simplified tickets")
    print(f"Will delete {len(issues_to_delete)} issues\n")
    
    if len(issues_to_delete) == 0:
        print("No issues to delete.")
        return
    
    # Show what will be deleted
    print("Issues to be deleted (first 20):")
    for issue in issues_to_delete[:20]:
        print(f"  {issue.key}: {issue.fields.summary[:60]}")
    if len(issues_to_delete) > 20:
        print(f"  ... and {len(issues_to_delete) - 20} more")
    
    # Auto-confirm (no prompt)
    print(f"\n⚠️  Deleting {len(issues_to_delete)} issues (keeping {len(KEEP_TICKETS)} simplified tickets)...")
    
    # Delete issues
    print("\n🗑️  Deleting issues...")
    deleted = 0
    failed = 0
    
    for i, issue in enumerate(issues_to_delete, 1):
        try:
            issue.delete()
            deleted += 1
            if deleted % 10 == 0:
                print(f"  Progress: {deleted}/{len(issues_to_delete)} deleted...")
        except Exception as e:
            print(f"  ✗ Failed to delete {issue.key}: {e}")
            failed += 1
    
    print(f"\n✓ Deletion complete!")
    print(f"  - Deleted: {deleted}")
    print(f"  - Failed: {failed}")
    print(f"\n✓ Kept {len(KEEP_TICKETS)} simplified tickets:")
    print(f"  Epics: KAN-9, KAN-402-406")
    print(f"  Stories: KAN-442-448")
    print(f"  Tasks: KAN-449-455")

if __name__ == '__main__':
    main()
