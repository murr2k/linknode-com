#!/bin/bash
# Script to install Playwright and its dependencies

echo "Installing Playwright E2E Testing Dependencies..."
echo "=============================================="

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo "Error: npm is not installed. Please install Node.js first."
    exit 1
fi

# Install npm dependencies
echo "Installing npm packages..."
npm install

# Install Playwright browsers
echo ""
echo "Installing Playwright browsers..."
echo "Note: This may require sudo access for system dependencies."
echo ""

# Try to install without sudo first
npx playwright install

# Check if installation was successful
if [ $? -ne 0 ]; then
    echo ""
    echo "Browser installation failed. Trying with system dependencies..."
    echo "You may be prompted for your sudo password."
    echo ""
    
    # Try to install system dependencies
    sudo npx playwright install-deps
    
    # Try browser installation again
    npx playwright install
fi

echo ""
echo "Installation complete!"
echo ""
echo "You can now run tests with:"
echo "  npm test                    # Run all tests"
echo "  npm run test:headed         # Run with visible browser"
echo "  npm run test:ui            # Run with Playwright UI"
echo "  npm run test:debug         # Debug tests"
echo ""