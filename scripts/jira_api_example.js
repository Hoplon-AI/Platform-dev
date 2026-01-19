/**
 * JavaScript example for creating Jira tickets using REST API
 * 
 * This can be used with Node.js or in a browser console if you have
 * the Atlassian extension installed.
 * 
 * Usage:
 *   node scripts/jira_api_example.js
 * 
 * Or use with Atlassian extension in VS Code/Cursor
 */

const fs = require('fs');
const path = require('path');
const csv = require('csv-parser');

// Configuration - Update these values
const JIRA_SERVER = 'https://equirisk.atlassian.net';
const JIRA_PROJECT_KEY = 'KAN';
const JIRA_EMAIL = process.env.JIRA_EMAIL || 'your-email@example.com';
const JIRA_API_TOKEN = process.env.JIRA_API_TOKEN || 'your-api-token';

const CSV_FILE = path.join(__dirname, '../docs/jira-tickets-import.csv');

/**
 * Create a Jira ticket using REST API
 */
async function createJiraTicket(ticketData, auth) {
    const url = `${JIRA_SERVER}/rest/api/3/issue`;
    
    const issueData = {
        fields: {
            project: {
                key: JIRA_PROJECT_KEY
            },
            summary: ticketData.Summary,
            description: {
                type: 'doc',
                version: 1,
                content: [
                    {
                        type: 'paragraph',
                        content: [
                            {
                                text: ticketData.Description || '',
                                type: 'text'
                            }
                        ]
                    }
                ]
            },
            issuetype: {
                name: ticketData['Issue Type']
            }
        }
    };
    
    // Add priority
    if (ticketData.Priority) {
        const priorityMap = {
            'P0': 'Highest',
            'P1': 'High',
            'P2': 'Medium',
            'P3': 'Low'
        };
        issueData.fields.priority = {
            name: priorityMap[ticketData.Priority] || 'Medium'
        };
    }
    
    // Add labels
    if (ticketData.Labels) {
        issueData.fields.labels = ticketData.Labels.split(',').map(l => l.trim());
    }
    
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Authorization': `Basic ${auth}`,
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify(issueData)
        });
        
        if (!response.ok) {
            const error = await response.text();
            throw new Error(`HTTP ${response.status}: ${error}`);
        }
        
        const result = await response.json();
        return result.key;
    } catch (error) {
        console.error(`Failed to create ticket "${ticketData.Summary}":`, error);
        return null;
    }
}

/**
 * Read CSV and create tickets
 */
async function createTicketsFromCSV() {
    const tickets = [];
    
    return new Promise((resolve, reject) => {
        fs.createReadStream(CSV_FILE)
            .pipe(csv())
            .on('data', (row) => tickets.push(row))
            .on('end', () => resolve(tickets))
            .on('error', reject);
    });
}

/**
 * Main function
 */
async function main() {
    console.log('='.repeat(60));
    console.log('Jira Ticket Creation via REST API');
    console.log('='.repeat(60));
    
    // Create Basic Auth header
    const auth = Buffer.from(`${JIRA_EMAIL}:${JIRA_API_TOKEN}`).toString('base64');
    
    // Read tickets from CSV
    console.log('\n📖 Reading tickets from CSV...');
    const tickets = await createTicketsFromCSV();
    console.log(`✓ Found ${tickets.length} tickets`);
    
    // Group by type
    const epics = tickets.filter(t => t['Issue Type'] === 'Epic');
    const stories = tickets.filter(t => t['Issue Type'] === 'Story');
    const tasks = tickets.filter(t => t['Issue Type'] === 'Task');
    
    console.log(`  - Epics: ${epics.length}`);
    console.log(`  - Stories: ${stories.length}`);
    console.log(`  - Tasks: ${tasks.length}`);
    
    // Confirm
    console.log(`\n⚠️  About to create ${tickets.length} tickets in project ${JIRA_PROJECT_KEY}`);
    const readline = require('readline');
    const rl = readline.createInterface({
        input: process.stdin,
        output: process.stdout
    });
    
    const answer = await new Promise(resolve => {
        rl.question('Continue? (yes/no): ', resolve);
    });
    rl.close();
    
    if (answer.toLowerCase() !== 'yes' && answer.toLowerCase() !== 'y') {
        console.log('Cancelled.');
        return;
    }
    
    // Create Epics first
    console.log('\n📋 Creating Epics...');
    const epicKeys = {};
    for (const epic of epics) {
        const key = await createJiraTicket(epic, auth);
        if (key) {
            epicKeys[epic.Summary] = key;
            console.log(`  ✓ Created: ${key} - ${epic.Summary}`);
        }
    }
    
    // Create Stories
    console.log('\n📖 Creating Stories...');
    const storyKeys = {};
    for (const story of stories) {
        const key = await createJiraTicket(story, auth);
        if (key) {
            storyKeys[story.Summary] = key;
            console.log(`  ✓ Created: ${key} - ${story.Summary}`);
        }
    }
    
    // Create Tasks
    console.log('\n✅ Creating Tasks...');
    let taskCount = 0;
    for (const task of tasks) {
        const key = await createJiraTicket(task, auth);
        if (key) {
            taskCount++;
            if (taskCount % 10 === 0) {
                console.log(`  Progress: ${taskCount} tasks created...`);
            }
        }
    }
    
    console.log(`\n✓ Ticket creation complete!`);
    console.log(`  - Epics: ${Object.keys(epicKeys).length}`);
    console.log(`  - Stories: ${Object.keys(storyKeys).length}`);
    console.log(`  - Tasks: ${taskCount}`);
    console.log(`\n  View board: ${JIRA_SERVER}/jira/software/projects/${JIRA_PROJECT_KEY}/boards/1`);
}

// Run if executed directly
if (require.main === module) {
    main().catch(console.error);
}

module.exports = { createJiraTicket, createTicketsFromCSV };
