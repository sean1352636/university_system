#!/bin/bash
# Clear Python cache and run university system

echo "🧹 Clearing Python bytecode cache..."
find university_system -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find university_system -name "*.pyc" -delete 2>/dev/null || true
find university_system -name "*.pyo" -delete 2>/dev/null || true

echo "✅ Cache cleared!"
echo ""
echo "🚀 Starting University System..."
python3 run.py --gui
