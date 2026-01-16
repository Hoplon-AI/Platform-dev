#!/usr/bin/env python3
"""
Script to delete Jira tickets created for the MVP roadmap.
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

def main():
    print("=" * 60)
    print("Delete Jira Tickets")
    print("=" * 60)
    
    try:
        jira = JIRA(server=JIRA_SERVER, basic_auth=(JIRA_EMAIL, JIRA_API_TOKEN))
        user = jira.current_user()
        print(f"✓ Connected as {user}\n")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        sys.exit(1)
    
    # Get all issues created today (keep KAN-9 as it was the test)
    print("Finding issues to delete...")
    issues = jira.search_issues('project=KAN AND created >= "2025-01-27" ORDER BY key', maxResults=500)
    
    # Filter out KAN-9 (the test epic we want to keep)
    issues_to_delete = [i for i in issues if i.key != 'KAN-9']
    
    print(f"Found {len(issues_to_delete)} issues to delete (keeping KAN-9)")
    print(f"Issue keys: {[i.key for i in issues_to_delete[:20]]}...")
    
    if len(issues_to_delete) == 0:
        print("No issues to delete.")
        return
    
    # Confirm
    response = input(f"\n⚠️  Delete {len(issues_to_delete)} issues? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Cancelled.")
        return
    
    # Delete issues
    print("\n🗑️  Deleting issues...")
    deleted = 0
    failed = 0
    
    for issue in issues_to_delete:
        try:
            issue.delete()
            deleted += 1
            if deleted % 10 == 0:
                print(f"  Progress: {deleted} deleted...")
        except Exception as e:
            print(f"  ✗ Failed to delete {issue.key}: {e}")
            failed += 1
    
    print(f"\n✓ Deletion complete!")
    print(f"  - Deleted: {deleted}")
    print(f"  - Failed: {failed}")

if __name__ == '__main__':
    main()
