# Jira Ticket Creation Guide

This guide explains how to create Jira tickets for the MVP roadmap using various methods.

## Prerequisites

1. **Jira Access**: You need access to the EquiRisk Jira instance
   - URL: https://equirisk.atlassian.net
   - Project: KAN

2. **API Token**: Generate a Jira API token
   - Go to: https://id.atlassian.com/manage-profile/security/api-tokens
   - Click "Create API token"
   - Copy the token (you'll need it for API access)

## Method 1: Using Python Script (Recommended)

### Setup

1. Install required packages:
```bash
pip install jira python-dotenv
```

2. Create `.env` file in project root:
```bash
cp .env.example .env
```

3. Edit `.env` and add your credentials:
```
JIRA_SERVER=https://equirisk.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-api-token-here
JIRA_PROJECT_KEY=KAN
```

### Run Script

```bash
# Using Python directly
python3 scripts/create_jira_tickets.py

# Or using the shell script
./scripts/create_jira_tickets.sh
```

The script will:
- Connect to Jira
- Read tickets from `docs/jira-tickets-import.csv`
- Create Epics first
- Create Stories (linked to Epics)
- Create Tasks (linked to Stories)
- Show progress and results

## Method 2: Using CSV Import in Jira UI

1. **Prepare CSV File**:
   - File location: `docs/jira-tickets-import.csv`
   - Contains all tickets with proper formatting

2. **Import in Jira**:
   - Go to your Jira project: https://equirisk.atlassian.net/jira/software/projects/KAN
   - Click **Project Settings** (gear icon)
   - Go to **Import & Export** → **CSV Import**
   - Upload `docs/jira-tickets-import.csv`
   - Map CSV columns to Jira fields:
     - `Summary` → Summary
     - `Issue Type` → Issue Type
     - `Description` → Description
     - `Priority` → Priority
     - `Story Points` → Story Points
     - `Labels` → Labels
     - `Components` → Components
   - Review and import

3. **Link Epics and Stories**:
   - After import, manually link Stories to Epics using Epic Link field
   - Or use bulk edit to link multiple stories at once

## Method 3: Using Atlassian Extension in VS Code/Cursor

If you have the Atlassian extension installed:

1. **Authenticate**:
   - Open Command Palette (Cmd+Shift+P / Ctrl+Shift+P)
   - Type "Jira: Authenticate"
   - Follow the authentication flow

2. **Create Tickets**:
   - Open Command Palette
   - Type "Jira: Create Issue"
   - Fill in the ticket details
   - Or use the extension's UI to create tickets

3. **Bulk Create** (if extension supports):
   - Some extensions support bulk creation
   - Check extension documentation for bulk import features

## Method 4: Using Jira REST API Directly

### Using curl

```bash
# Create an Epic
curl -X POST \
  'https://equirisk.atlassian.net/rest/api/3/issue' \
  -H 'Authorization: Basic BASE64_ENCODED_EMAIL:API_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{
    "fields": {
      "project": {"key": "KAN"},
      "summary": "Frontend Infrastructure & UPRN Mapping Service",
      "issuetype": {"name": "Epic"},
      "description": {
        "type": "doc",
        "version": 1,
        "content": [{
          "type": "paragraph",
          "content": [{
            "type": "text",
            "text": "Set up React frontend application, base components, and implement UPRN mapping service using OS DataHub API"
          }]
        }]
      }
    }
  }'
```

### Using JavaScript/Node.js

See `scripts/jira_api_example.js` for a complete example.

## Method 5: Manual Creation

Use the detailed breakdown in `docs/jira-tickets-import.md` to create tickets manually:

1. **Create Epics First**:
   - Go to your Jira board
   - Click "Create" → Select "Epic"
   - Fill in details from the markdown file

2. **Create Stories**:
   - Link each Story to its Epic using Epic Link field
   - Add Story Points, Priority, Labels, Components

3. **Create Tasks**:
   - Link Tasks to their parent Stories
   - Add Priority, Labels, Components

## Ticket Structure

The tickets are organized as follows:

- **6 Epics** (one per major feature area)
  - Epic 1: Frontend Infrastructure & UPRN Mapping Service
  - Epic 2: Portfolio Overview Dashboard
  - Epic 3: Block View Implementation
  - Epic 4: HA Profile Page with Interactive Map
  - Epic 5: Analytics & Reporting Dashboard
  - Epic 6: Excel Table Views Integration

- **33 Stories** (grouped by functionality)
- **150+ Tasks** (detailed implementation tasks)
- **28 API Endpoint Tasks**
- **8 Database Tasks**
- **9 Testing Tasks**
- **5 Documentation Tasks**

**Total: ~200+ tickets**

## Custom Fields

Your Jira instance may have different custom field IDs. Common fields:

- **Epic Name**: `customfield_10011`
- **Epic Link**: `customfield_10014`
- **Story Points**: `customfield_10016`

To find your custom field IDs:
1. Go to Jira Settings → Issues → Custom Fields
2. Click on a field to see its ID in the URL
3. Update the script with your field IDs

## Troubleshooting

### Authentication Errors
- Verify your email and API token are correct
- Check that your account has permission to create issues in the KAN project

### Field Errors
- Some custom fields may not exist in your Jira instance
- The script will skip fields that don't exist
- You may need to manually set Epic Links after creation

### Rate Limiting
- Jira has rate limits on API calls
- The script includes basic error handling
- If you hit rate limits, wait a few minutes and retry

### Missing Components
- Create Components in Jira first:
  - Frontend
  - Backend
  - API
  - Database
  - Testing
  - Documentation

## Next Steps After Creation

1. **Add to Board**:
   - Go to: https://equirisk.atlassian.net/jira/software/projects/KAN/boards/1
   - Tickets should appear automatically
   - Organize into columns (To Do, In Progress, Done)

2. **Link Stories to Epics**:
   - If not linked automatically, use bulk edit to link Stories to Epics

3. **Assign Tickets**:
   - Assign tickets to team members
   - Set due dates if needed

4. **Set Up Sprints**:
   - Create sprints for each week
   - Add tickets to sprints

## Support

If you encounter issues:
1. Check Jira API documentation: https://developer.atlassian.com/cloud/jira/platform/rest/v3/
2. Verify your Jira instance configuration
3. Check the script error messages for specific issues
