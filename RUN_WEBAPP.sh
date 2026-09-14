#!/bin/bash

# Wildfire Impact Calculator - Web App Launcher
# Starts the Flask development server

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     Wildfire Impact Calculator - Web Application              ║"
echo "║                                                                ║"
echo "║  Starting Flask server on http://localhost:5000               ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Activate virtual environment
source venv/bin/activate

# Check if dependencies are installed
python3 -c "import flask" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing Flask dependencies..."
    pip install -q -r requirements-webapp.txt
fi

echo "✓ Environment ready"
echo ""
echo "Starting Flask server..."
echo ""
echo "📊 Dashboard: http://localhost:5000"
echo "📁 Data folder: $(pwd)"
echo "🔥 Dataset: BDIFF 2025 (21,141 fires, 31,744 ha)"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Run Flask app
python3 app.py
