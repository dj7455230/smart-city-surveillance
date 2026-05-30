"""
CrimeWatch AI v2 — Production Entry Point
Run: python3 app.py
"""

import os, asyncio, logging
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("crimewatch")


@asynccontextmanager
async def lifespan(app):
    logger.info("Starting CrimeWatch AI v2...")

    # Ensure directories exist
    for d in ["evidence", "uploads", "criminal_db", "data", "models"]:
        Path(d).mkdir(exist_ok=True)

    # Database
    from backend.database.models import init_db
    await init_db()
    logger.info("Database ready")

    # AI Detector
    from backend.ai.detector import CrimeDetector
    from backend.api import routes as r
    r.detector = CrimeDetector(
        model_path=os.getenv("MODEL_PATH", "yolov8n.pt"),
        confidence=float(os.getenv("CONFIDENCE_THRESHOLD", "0.45")),
        enable_face=True,
        enable_anpr=True,
        enable_crowd=True,
        enable_night_vision=True,
    )
    logger.info("AI detector ready")

    # Alert Manager
    from backend.alerts.alert_manager import AlertManager
    r.alert_manager = AlertManager()
    logger.info("Alert manager ready")

    # Crime Predictor
    from backend.ai.crime_predictor import CrimePredictor
    r.crime_predictor = CrimePredictor()
    logger.info("Crime predictor ready")

    # Audio (optional)
    if os.getenv("AUDIO_DETECTION_ENABLED", "false").lower() == "true":
        from backend.ai.audio_detector import AudioDetector
        audio = AudioDetector()
        async def _on_audio(alert):
            await r.alert_manager.broadcast_ws(alert)
        audio.start_monitoring(callback=_on_audio)
        logger.info("Audio detector started")

    # Seed demo data
    await _seed_all()

    logger.info("=" * 50)
    logger.info("  CrimeWatch AI v2 is LIVE")
    logger.info("  API:      http://localhost:8000")
    logger.info("  Docs:     http://localhost:8000/docs")
    logger.info("  Frontend: http://localhost:3000")
    logger.info("=" * 50)

    yield
    logger.info("Shutting down...")


async def _seed_all():
    """Seed all demo data into database on first run"""
    import random
    from datetime import datetime, timedelta
    from backend.database.models import (
        AsyncSessionLocal, Alert, Vehicle,
        CriminalProfile, StolenVehicle
    )
    from sqlalchemy import select, func

    async with AsyncSessionLocal() as db:
        # Only seed if empty
        count = await db.scalar(select(func.count(Alert.id)))
        if count and count > 0:
            return

        # ── Alerts ────────────────────────────────────────────────────────────
        crime_types = ["fight","weapon","accident","suspicious","riot","criminal","stolen_vehicle","loitering"]
        severities  = {
            "fight":"HIGH","weapon":"CRITICAL","accident":"HIGH",
            "suspicious":"MEDIUM","riot":"CRITICAL","criminal":"CRITICAL",
            "stolen_vehicle":"HIGH","loitering":"MEDIUM",
        }
        cameras  = [f"CAM-{i:02d}" for i in range(1, 9)]
        vehicles = ["VH-001","VH-002","VH-003","VH-004"]
        base_lat, base_lng = 28.6139, 77.2090

        for i in range(60):
            ct = random.choice(crime_types)
            db.add(Alert(
                timestamp    = datetime.utcnow() - timedelta(hours=random.randint(0, 120)),
                crime_type   = ct,
                confidence   = round(random.uniform(0.60, 0.97), 2),
                severity     = severities[ct],
                latitude     = round(base_lat + random.uniform(-0.07, 0.07), 6),
                longitude    = round(base_lng + random.uniform(-0.07, 0.07), 6),
                camera_id    = random.choice(cameras),
                vehicle_id   = random.choice(vehicles),
                snapshot_path= "",
                alert_sent   = True,
                resolved     = random.choice([True, True, False]),
                person_count = random.randint(1, 5),
                vehicle_count= random.randint(0, 2),
                crowd_risk   = round(random.uniform(0, 0.9), 2) if ct == "riot" else 0.0,
                night_mode   = random.choice([True, False]),
            ))

        # ── Vehicles ──────────────────────────────────────────────────────────
        for v in [
            ("VH-001","Patrol Alpha",  "Rajan Kumar",  "DL-1042"),
            ("VH-002","Patrol Bravo",  "Priya Singh",  "DL-1087"),
            ("VH-003","Patrol Charlie","Amit Sharma",  "DL-1103"),
            ("VH-004","Patrol Delta",  "Sunita Verma", "DL-1156"),
        ]:
            db.add(Vehicle(
                vehicle_id=v[0], name=v[1], status="active",
                latitude=base_lat, longitude=base_lng,
                camera_count=4, officer_name=v[2], badge_number=v[3],
            ))

        # ── Criminal Profiles ─────────────────────────────────────────────────
        for name, alias, history, risk in [
            ("Rahul Verma",   "Raju",    "Armed robbery 2022, assault 2023", "CRITICAL"),
            ("Suresh Pandey", "Kalu",    "Drug trafficking 2021",            "HIGH"),
            ("Demo Suspect",  "Unknown", "Test profile for demo",            "MEDIUM"),
        ]:
            db.add(CriminalProfile(
                name=name, alias=alias, crime_history=history, risk_level=risk
            ))

        # ── Stolen Vehicles ───────────────────────────────────────────────────
        for plate, make, model, color, status, reason, priority in [
            ("DL01AB1234","Honda",   "City",   "White",  "stolen",  "Reported stolen Jan 2024",  "HIGH"),
            ("MH12XY5678","Toyota",  "Innova", "Black",  "stolen",  "Reported stolen Feb 2024",  "HIGH"),
            ("UP32CD9012","Maruti",  "Swift",  "Red",    "stolen",  "Reported stolen Mar 2024",  "MEDIUM"),
            ("KA05EF3456","Hyundai", "i20",    "Blue",   "stolen",  "Reported stolen Apr 2024",  "MEDIUM"),
            ("RJ14IJ2345","Tata",    "Nexon",  "Grey",   "wanted",  "Robbery suspect vehicle",   "CRITICAL"),
            ("GJ01KL6789","Mahindra","Scorpio","Black",  "wanted",  "Drug trafficking vehicle",  "CRITICAL"),
        ]:
            db.add(StolenVehicle(
                plate_number=plate, vehicle_make=make, vehicle_model=model,
                color=color, status=status, reason=reason, priority=priority,
                reported_by="Delhi Police",
            ))

        await db.commit()
        logger.info("Demo data seeded: 60 alerts, 4 vehicles, 3 criminals, 6 stolen vehicles")


# ── FastAPI App ───────────────────────────────────────────────────────────────

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI(
    title="CrimeWatch AI",
    description="Real-time crime detection system",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from backend.api.routes import router
app.include_router(router)

frontend_build = Path("frontend/dashboard/dist")
if frontend_build.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_build / "assets")), name="assets")

@app.get("/")
@app.get("/{full_path:path}")
async def serve_spa(full_path: str = ""):
    index = frontend_build / "index.html"
    if index.exists() and not full_path.startswith(("api", "ws")):
        return FileResponse(str(index))
    return {"status": "CrimeWatch AI v2", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "8000")),
        reload=True,
        log_level="info",
    )
