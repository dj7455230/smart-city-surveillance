#!/bin/bash
# CrimeWatch AI v2 — One-click setup

set -e

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║     CrimeWatch AI v2 — Full Feature Setup           ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# Python backend
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Copy env
if [ ! -f .env ]; then
  cp .env.example .env
  echo "✓ Created .env (edit with your API keys)"
fi

# Directories
mkdir -p evidence uploads criminal_db data models

# Frontend
echo ""
echo "📦 Installing frontend dependencies..."
cd frontend/dashboard
npm install
echo "✓ Frontend ready"
cd ../..

# Demo video
echo ""
echo "🎬 Generating demo video..."
python simulation/generate_test_video.py

# Pre-train crime predictor
echo ""
echo "🧠 Pre-training crime prediction model..."
python -c "
from backend.ai.crime_predictor import CrimePredictor
p = CrimePredictor()
print('  ✓ Model trained and saved')
"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  ✅ Setup complete!                                  ║"
echo "║                                                      ║"
echo "║  1. Edit .env with your API keys (optional)          ║"
echo "║                                                      ║"
echo "║  2. Start backend:                                   ║"
echo "║     python app.py                                    ║"
echo "║                                                      ║"
echo "║  3. Start frontend (new terminal):                   ║"
echo "║     cd frontend/dashboard && npm run dev             ║"
echo "║                                                      ║"
echo "║  4. Run demo simulation (new terminal):              ║"
echo "║     python simulation/demo_runner.py                 ║"
echo "║                                                      ║"
echo "║  Dashboard:  http://localhost:3000                   ║"
echo "║  API Docs:   http://localhost:8000/docs              ║"
echo "║                                                      ║"
echo "║  Features:                                           ║"
echo "║  ✓ YOLOv8 Detection    ✓ Face Recognition           ║"
echo "║  ✓ ANPR Plate Scan     ✓ Crowd Analysis             ║"
echo "║  ✓ Night Vision        ✓ Crime Prediction AI        ║"
echo "║  ✓ Audio Detection     ✓ WhatsApp + Telegram        ║"
echo "║  ✓ Evidence Vault      ✓ Multi-language Alerts      ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
