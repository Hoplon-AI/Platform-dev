#!/usr/bin/env python3
"""
Simplified script to create Jira tickets without custom fields that may not exist.
Creates tickets and logs any that need manual Epic linking.
"""

import os
import csv
import sys
import time
from pathlib import Path

try:
    from jira import JIRA
except ImportError:
    print("Error: jira package not installed. Run: pip install jira")
    sys.exit(1)

JIRA_SERVER = os.getenv('JIRA_SERVER', 'https://equirisk.atlassian.net')
JIRA_EMAIL = os.getenv('JIRA_EMAIL')
JIRA_API_TOKEN = os.getenv('JIRA_API_TOKEN')
JIRA_PROJECT_KEY = os.getenv('JIRA_PROJECT_KEY', 'KAN')

CSV_FILE = Path(__file__).parent.parent / 'docs' / 'jira-tickets-import.csv'

def create_epic(jira, epic_data):
    """Create an Epic."""
    try:
        issue_dict = {
            'project': {'key': JIRA_PROJECT_KEY},
            'summary': epic_data['Summary'],
            'description': epic_data.get('Description', ''),
            'issuetype': {'name': 'Epic'},
        }
        
        if epic_data.get('Priority'):
            priority_map = {'P0': 'Highest', 'P1': 'High', 'P2': 'Medium', 'P3': 'Low'}
            priority_name = priority_map.get(epic_data['Priority'], 'Medium')
            issue_dict['priority'] = {'name': priority_name}
        
        new_epic = jira.create_issue(fields=issue_dict)
        print(f"  ✓ Created Epic: {new_epic.key}")
        return new_epic.key
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return None

def create_story(jira, story_data, epic_key=None):
    """Create a Story (without Epic Link initially)."""
    try:
        issue_dict = {
            'project': {'key': JIRA_PROJECT_KEY},
            'summary': story_data['Summary'],
            'description': story_data.get('Description', ''),
            'issuetype': {'name': 'Story'},
        }
        
        if story_data.get('Priority'):
            priority_map = {'P0': 'Highest', 'P1': 'High', 'P2': 'Medium', 'P3': 'Low'}
            priority_name = priority_map.get(story_data['Priority'], 'Medium')
            issue_dict['priority'] = {'name': priority_name}
        
        new_story = jira.create_issue(fields=issue_dict)
        
        # Add labels if provided
        if story_data.get('Labels'):
            labels = [l.strip() for l in story_data['Labels'].split(',')]
            try:
                new_story.update(fields={'labels': labels})
            except:
                pass
        
        print(f"  ✓ Created Story: {new_story.key}")
        return new_story.key, epic_key  # Return epic_key for manual linking
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return None, None

def create_task(jira, task_data, parent_key=None):
    """Create a Task."""
    try:
        issue_dict = {
            'project': {'key': JIRA_PROJECT_KEY},
            'summary': task_data['Summary'],
            'description': task_data.get('Description', ''),
            'issuetype': {'name': 'Task'},
        }
        
        if task_data.get('Priority'):
            priority_map = {'P0': 'Highest', 'P1': 'High', 'P2': 'Medium', 'P3': 'Low'}
            priority_name = priority_map.get(task_data['Priority'], 'Medium')
            issue_dict['priority'] = {'name': priority_name}
        
        if parent_key:
            issue_dict['parent'] = {'key': parent_key}
        
        new_task = jira.create_issue(fields=issue_dict)
        
        # Add labels if provided
        if task_data.get('Labels'):
            labels = [l.strip() for l in task_data['Labels'].split(',')]
            try:
                new_task.update(fields={'labels': labels})
            except:
                pass
        
        return new_task.key
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return None

def main():
    print("=" * 60)
    print("Jira Ticket Creation (Simplified)")
    print("=" * 60)
    
    if not JIRA_API_TOKEN:
        print("Error: JIRA_API_TOKEN not set")
        sys.exit(1)
    
    try:
        jira = JIRA(server=JIRA_SERVER, basic_auth=(JIRA_EMAIL, JIRA_API_TOKEN))
        user = jira.current_user()
        print(f"✓ Connected as {user}\n")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        sys.exit(1)
    
    # Read CSV
    tickets = []
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        tickets = list(reader)
    
    print(f"✓ Read {len(tickets)} tickets from CSV\n")
    
    # Check for existing Epic
    epics = {}
    try:
        existing = jira.issue('KAN-9')
        if existing.fields.issuetype.name == 'Epic':
            epics['Frontend Infrastructure & UPRN Mapping Service'] = 'KAN-9'
            print("✓ Found existing Epic: KAN-9\n")
    except:
        pass
    
    # Create Epics
    print("📋 Creating Epics...")
    for ticket in tickets:
        if ticket['Issue Type'] == 'Epic':
            if ticket['Summary'] == 'Frontend Infrastructure & UPRN Mapping Service' and 'KAN-9' in epics.values():
                print(f"  ⊙ Skipping (exists): KAN-9")
                continue
            key = create_epic(jira, ticket)
            if key:
                epics[ticket['Summary']] = key
            time.sleep(0.5)
    
    # Create Stories
    print("\n📖 Creating Stories...")
    stories = {}
    epic_links = []  # Store for manual linking
    story_count = 0
    
    for ticket in tickets:
        if ticket['Issue Type'] == 'Story':
            epic_key = None
            if ticket.get('Epic Link'):
                epic_name = ticket['Epic Link']
                if epic_name.startswith('KAN-EPIC-'):
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
            
            story_key, epic = create_story(jira, ticket, epic_key)
            if story_key:
                stories[ticket['Summary']] = story_key
                if epic:
                    epic_links.append((story_key, epic))
                story_count += 1
                if story_count % 5 == 0:
                    print(f"  Progress: {story_count} stories...")
            time.sleep(0.3)
    
    # Create Tasks
    print("\n✅ Creating Tasks...")
    task_count = 0
    total_tasks = len([t for t in tickets if t['Issue Type'] == 'Task'])
    
    for ticket in tickets:
        if ticket['Issue Type'] == 'Task':
            parent_key = None
            # Simple parent matching
            for story_summary, story_key in stories.items():
                if story_summary[:30] in ticket.get('Summary', ''):
                    parent_key = story_key
                    break
            
            if create_task(jira, ticket, parent_key):
                task_count += 1
                if task_count % 20 == 0:
                    print(f"  Progress: {task_count}/{total_tasks} tasks...")
            time.sleep(0.2)
    
    print(f"\n✓ Creation complete!")
    print(f"  - Epics: {len(epics)}")
    print(f"  - Stories: {story_count}")
    print(f"  - Tasks: {task_count}")
    print(f"\n⚠️  Note: Epic links may need to be set manually in Jira UI")
    print(f"  View board: {JIRA_SERVER}/jira/software/projects/{JIRA_PROJECT_KEY}/boards/1")

if __name__ == '__main__':
    main()
