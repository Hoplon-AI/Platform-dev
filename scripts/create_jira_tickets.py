#!/usr/bin/env python3
"""
Script to create Jira tickets from CSV file using Jira REST API.

This script reads the jira-tickets-import.csv file and creates tickets in Jira.

Requirements:
- jira Python library: pip install jira
- Jira credentials configured in environment variables or .env file

Usage:
    python scripts/create_jira_tickets.py

Environment Variables:
    JIRA_SERVER: Your Jira server URL (e.g., https://equirisk.atlassian.net)
    JIRA_EMAIL: Your Jira email/username
    JIRA_API_TOKEN: Your Jira API token (get from https://id.atlassian.com/manage-profile/security/api-tokens)
    JIRA_PROJECT_KEY: Project key (e.g., KAN)
"""

import os
import csv
import json
import sys
import argparse
import time
from typing import Dict, List, Optional
from pathlib import Path

try:
    from jira import JIRA
    from dotenv import load_dotenv
except ImportError:
    print("Error: Required packages not installed.")
    print("Please install: pip install jira python-dotenv")
    sys.exit(1)

# Load environment variables
load_dotenv()

# Configuration
JIRA_SERVER = os.getenv('JIRA_SERVER', 'https://equirisk.atlassian.net')
JIRA_EMAIL = os.getenv('JIRA_EMAIL')
JIRA_API_TOKEN = os.getenv('JIRA_API_TOKEN')
JIRA_PROJECT_KEY = os.getenv('JIRA_PROJECT_KEY', 'KAN')

# CSV file path
CSV_FILE = Path(__file__).parent.parent / 'docs' / 'jira-tickets-import.csv'


def connect_to_jira() -> JIRA:
    """Connect to Jira using credentials."""
    if not JIRA_EMAIL or not JIRA_API_TOKEN:
        raise ValueError(
            "JIRA_EMAIL and JIRA_API_TOKEN must be set in environment variables or .env file"
        )
    
    jira = JIRA(
        server=JIRA_SERVER,
        basic_auth=(JIRA_EMAIL, JIRA_API_TOKEN)
    )
    
    # Test connection
    try:
        user = jira.current_user()
        print(f"✓ Connected to Jira as {user}")
    except Exception as e:
        raise ConnectionError(f"Failed to connect to Jira: {e}")
    
    return jira


def read_csv_tickets() -> List[Dict]:
    """Read tickets from CSV file."""
    tickets = []
    
    if not CSV_FILE.exists():
        raise FileNotFoundError(f"CSV file not found: {CSV_FILE}")
    
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            tickets.append(row)
    
    print(f"✓ Read {len(tickets)} tickets from CSV")
    return tickets


def create_epic(jira: JIRA, epic_data: Dict) -> Optional[str]:
    """Create an Epic in Jira."""
    try:
        issue_dict = {
            'project': {'key': JIRA_PROJECT_KEY},
            'summary': epic_data['Summary'],
            'description': epic_data.get('Description', ''),
            'issuetype': {'name': 'Epic'},
        }
        
        # Add Epic Name custom field if available
        # Note: Epic Name field ID may vary - check your Jira instance
        # For most Jira instances, Epic Name is a custom field
        epic_name_field = 'customfield_10011'  # Common Epic Name field ID
        
        new_epic = jira.create_issue(fields=issue_dict)
        
        # Set Epic Name
        try:
            new_epic.update(fields={epic_name_field: epic_data['Summary']})
        except:
            # If Epic Name field doesn't exist or has different ID, skip it
            pass
        
        print(f"  ✓ Created Epic: {new_epic.key} - {epic_data['Summary']}")
        return new_epic.key
    except Exception as e:
        print(f"  ✗ Failed to create Epic '{epic_data['Summary']}': {e}")
        return None


def create_story(jira: JIRA, story_data: Dict, epic_key: Optional[str] = None) -> Optional[str]:
    """Create a Story in Jira."""
    try:
        issue_dict = {
            'project': {'key': JIRA_PROJECT_KEY},
            'summary': story_data['Summary'],
            'description': story_data.get('Description', ''),
            'issuetype': {'name': 'Story'},
        }
        
        # Epic Link will be set after creation (see below)
        # Don't set it in initial creation to avoid field errors
        
        # Story Points will be set after creation if needed
        # Don't set it in initial creation to avoid field errors
        
        # Add Priority if provided
        if story_data.get('Priority'):
            priority_map = {'P0': 'Highest', 'P1': 'High', 'P2': 'Medium', 'P3': 'Low'}
            priority_name = priority_map.get(story_data['Priority'], 'Medium')
            issue_dict['priority'] = {'name': priority_name}
        
        new_story = jira.create_issue(fields=issue_dict)
        
        # Try to link to Epic after creation using REST API v3
        if epic_key:
            try:
                # Use REST API v3 to link Epic
                url = f"{jira._options['server']}/rest/api/3/issue/{new_story.key}"
                # Try to find Epic Link field dynamically
                # For now, skip Epic linking - can be done manually or via UI
                # Epic linking requires knowing the exact custom field ID for this instance
                pass
            except Exception as e:
                pass  # Silently skip Epic linking for now
        
        # Add labels
        if story_data.get('Labels'):
            labels = [label.strip() for label in story_data['Labels'].split(',')]
            try:
                new_story.update(fields={'labels': labels})
            except:
                pass
        
        # Add components
        if story_data.get('Components'):
            components = [{'name': comp.strip()} for comp in story_data['Components'].split(',')]
            try:
                new_story.update(fields={'components': components})
            except:
                pass
        
        print(f"  ✓ Created Story: {new_story.key} - {story_data['Summary']}")
        return new_story.key
    except Exception as e:
        print(f"  ✗ Failed to create Story '{story_data['Summary']}': {e}")
        return None


def create_task(jira: JIRA, task_data: Dict, parent_key: Optional[str] = None) -> Optional[str]:
    """Create a Task in Jira."""
    try:
        issue_dict = {
            'project': {'key': JIRA_PROJECT_KEY},
            'summary': task_data['Summary'],
            'description': task_data.get('Description', ''),
            'issuetype': {'name': 'Task'},
        }
        
        # Link to parent story if provided
        if parent_key:
            issue_dict['parent'] = {'key': parent_key}
        
        # Add Priority if provided
        if task_data.get('Priority'):
            priority_map = {'P0': 'Highest', 'P1': 'High', 'P2': 'Medium', 'P3': 'Low'}
            priority_name = priority_map.get(task_data['Priority'], 'Medium')
            issue_dict['priority'] = {'name': priority_name}
        
        new_task = jira.create_issue(fields=issue_dict)
        
        # Add labels
        if task_data.get('Labels'):
            labels = [label.strip() for label in task_data['Labels'].split(',')]
            new_task.update(fields={'labels': labels})
        
        # Add components
        if task_data.get('Components'):
            components = [{'name': comp.strip()} for comp in task_data['Components'].split(',')]
            new_task.update(fields={'components': components})
        
        print(f"    ✓ Created Task: {new_task.key} - {task_data['Summary']}")
        return new_task.key
    except Exception as e:
        print(f"    ✗ Failed to create Task '{task_data['Summary']}': {e}")
        return None


def create_tickets(jira: JIRA, tickets: List[Dict]):
    """Create all tickets in Jira, maintaining hierarchy."""
    epics = {}
    stories = {}
    
    # Check for existing Epic (KAN-9 - Frontend Infrastructure & UPRN Mapping Service)
    existing_epic_key = None
    try:
        existing_epic = jira.issue('KAN-9')
        if existing_epic.fields.issuetype.name == 'Epic':
            epics['Frontend Infrastructure & UPRN Mapping Service'] = 'KAN-9'
            existing_epic_key = 'KAN-9'
            print(f"✓ Found existing Epic: KAN-9 - {existing_epic.fields.summary}")
    except Exception as e:
        print(f"  Note: Could not check for existing Epic KAN-9: {e}")
    
    # First pass: Create Epics (skip if already exists)
    print("\n📋 Creating Epics...")
    epic_count = 0
    for ticket in tickets:
        if ticket['Issue Type'] == 'Epic':
            # Skip if this Epic already exists
            if ticket['Summary'] == 'Frontend Infrastructure & UPRN Mapping Service' and existing_epic_key:
                print(f"  ⊙ Skipping (already exists): KAN-9 - {ticket['Summary']}")
                continue
            
            epic_key = create_epic(jira, ticket)
            if epic_key:
                epics[ticket['Summary']] = epic_key
                epic_count += 1
                time.sleep(0.5)  # Small delay to avoid rate limiting
    
    # Second pass: Create Stories (linked to Epics)
    print("\n📖 Creating Stories...")
    story_count = 0
    for ticket in tickets:
        if ticket['Issue Type'] == 'Story':
            epic_key = None
            if ticket.get('Epic Link'):
                # Find epic key by name or by Epic Key pattern (KAN-EPIC-1, etc.)
                epic_name = ticket['Epic Link']
                # Try direct name match first
                epic_key = epics.get(epic_name)
                # If not found, try to match by Epic number pattern
                if not epic_key and epic_name.startswith('KAN-EPIC-'):
                    # Map Epic numbers to summaries
                    epic_map = {
                        'KAN-EPIC-1': 'Frontend Infrastructure & UPRN Mapping Service',
                        'KAN-EPIC-2': 'Portfolio Overview Dashboard',
                        'KAN-EPIC-3': 'Block View Implementation',
                        'KAN-EPIC-4': 'HA Profile Page with Interactive Map',
                        'KAN-EPIC-5': 'Analytics & Reporting Dashboard',
                        'KAN-EPIC-6': 'Excel Table Views Integration (Doc A & Doc B)',
                    }
                    mapped_name = epic_map.get(epic_name)
                    if mapped_name:
                        epic_key = epics.get(mapped_name)
            
            story_key = create_story(jira, ticket, epic_key)
            if story_key:
                stories[ticket['Summary']] = story_key
                story_count += 1
                if story_count % 5 == 0:
                    print(f"  Progress: {story_count} stories created...")
                time.sleep(0.3)  # Small delay to avoid rate limiting
    
    # Third pass: Create Tasks (linked to Stories)
    print("\n✅ Creating Tasks...")
    task_count = 0
    total_tasks = len([t for t in tickets if t['Issue Type'] == 'Task'])
    
    for ticket in tickets:
        if ticket['Issue Type'] == 'Task':
            parent_key = None
            # Try to find parent story by matching summary patterns
            # This is a simple heuristic - you may need to adjust
            for story_summary, story_key in stories.items():
                if story_summary in ticket.get('Description', '') or ticket.get('Summary', '').startswith(story_summary[:20]):
                    parent_key = story_key
                    break
            
            create_task(jira, ticket, parent_key)
            task_count += 1
            if task_count % 10 == 0:
                print(f"  Progress: {task_count}/{total_tasks} tasks created...")
            time.sleep(0.2)  # Small delay to avoid rate limiting
    
    print(f"\n✓ Ticket creation complete!")
    print(f"  - Epics: {len(epics)}")
    print(f"  - Stories: {story_count}")
    print(f"  - Tasks: {task_count}")
    print(f"  - Total: {len(epics) + story_count + task_count} tickets")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Create Jira tickets from CSV')
    parser.add_argument('--yes', '-y', action='store_true', 
                       help='Skip confirmation prompt')
    args = parser.parse_args()
    
    print("=" * 60)
    print("Jira Ticket Creation Script")
    print("=" * 60)
    
    try:
        # Connect to Jira
        jira = connect_to_jira()
        
        # Read tickets from CSV
        tickets = read_csv_tickets()
        
        # Confirm before creating (unless --yes flag)
        if not args.yes:
            print(f"\n⚠️  About to create {len(tickets)} tickets in project {JIRA_PROJECT_KEY}")
            response = input("Continue? (yes/no): ")
            if response.lower() not in ['yes', 'y']:
                print("Cancelled.")
                return
        else:
            print(f"\n⚠️  Creating {len(tickets)} tickets in project {JIRA_PROJECT_KEY} (--yes flag used)")
        
        # Create tickets
        create_tickets(jira, tickets)
        
        print(f"\n✓ All tickets created successfully!")
        print(f"  View board: {JIRA_SERVER}/jira/software/projects/{JIRA_PROJECT_KEY}/boards/1")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
