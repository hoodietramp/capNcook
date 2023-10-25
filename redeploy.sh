#!/bin/bash

# Define your project directory (change this to the actual path)
PROJECT_DIR="/home/admin/capNcook/"

# GitHub repository URL
REPO_URL="https://github.com/hoodietramp/capNcook.git"

# Branch to pull from (e.g., master)
BRANCH="master"

# Navigate to the project directory
cd "$PROJECT_DIR"

# Update the code from the GitHub repository
git pull origin "$BRANCH"

# Install or update dependencies
pip3 install -r requirements.txt
sudo pip3 install -r requirements.txt

# Start system services
sudo systemctl restart capncook
