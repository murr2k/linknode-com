#!/bin/bash

# Script to update repository name from rackspace-k8s-demo to linknode-com

echo "Updating git remote URL..."
git remote set-url origin https://github.com/murr2k/linknode-com.git

echo "Verifying new remote URL..."
git remote -v

echo "Pushing to new repository..."
git push origin main

echo "Repository rename completed locally!"