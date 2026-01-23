#!/bin/bash
# Shell script to create Jira tickets using the Python script

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed"
    exit 1
fi

# Check if required packages are installed
if ! python3 -c "import jira" 2>/dev/null; then
    echo "Installing required packages..."
    pip3 install jira python-dotenv
fi

# Run the Python script
python3 "$(dirname "$0")/create_jira_tickets.py"
