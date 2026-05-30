"""
CrimeWatch AI - Production Backend Routes
"""
import asyncio, json, random, math, cv2, numpy as np, hashlib, os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, UploadFile, File, Depends, HTTPException, Form, Query
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, and_, or_
from pydantic import BaseModel

from backend.database.models import Alert, Vehicle, EvidenceLog, CriminalProfile, StolenVehicle, SystemLog, get_db

router = APIRouter()

detector = None
alert_manager = None
crime_predictor = None

DEMO_VEHICLES = [
    {"id": "VH-001", "name": "Patrol Alpha",   "lat": 28.6139, "lng": 77.2090, "officer": "Rajan Kumar",   "badge": "DL-1042"},
    {"id": "VH-002", "name": "Patrol Bravo",   "lat": 28.6200, "lng": 77.2150, "officer": "Priya Singh",   "badge": "DL-1087"},
    {"id": "VH-003", "name": "Patrol Charlie", "lat": 28.6080, "lng": 77.2020, "officer": "Amit Sharma",   "badge": "DL-1103"},
    {"id": "VH-004", "name": "Patrol Delta",   "lat": 28.6300, "lng": 77.1950, "officer": "Sunita Verma",  "badge": "DL-1156"},
]

def _gps(base_lat, base_lng, t, radius=0.003):
    return {
        "lat": round(base_lat + radius * math.sin(t * 0.07), 6),
        "lng": round(base_lng + radius * math.cos(t * 0.07), 6),
    }


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class AlertResolveRequest(BaseModel):
    notes: Optional[str] = None
    resolved_by: Optional[str] = "Officer"

class PlateCheckRequest(BaseModel):
    plate: str

class AddCriminalRequest(BaseModel):
    name: str
    alias: Optional[str] = None
    crime_history: Optional[str] = None
    risk_level: Optional[str] = "MEDIUM"
    notes: Optional[str] = None

# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/api/health")
async def health():
    return {
        "status": "online",
        "service": "CrimeWatch AI v2",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_since": datetime.utcnow().isoformat(),
        "features": {
            "yolo_detection": True,
            "face_recognition": detector.face_engine is not None if detector else False,
            "anpr": detector.anpr_engine is not None if detector else False,
            "crowd_analysis": detector.crowd_analyzer is not None if detector else False,
            "night_vision": detector.night_enhancer is not None if detector else False,
            "crime_prediction": crime_predictor is not None,
            "audio_detection": os.getenv("AUDIO_DETECTION_ENABLED","false") == "true",
        }
    }

# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/api/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    total      = await db.scalar(select(func.count(Alert.id))) or 0
    critical   = await db.scalar(select(func.count(Alert.id)).where(Alert.severity == "CRITICAL")) or 0
    high       = await db.scalar(select(func.count(Alert.id)).where(Alert.severity == "HIGH")) or 0
    unresolved = await db.scalar(select(func.count(Alert.id)).where(Alert.resolved == False)) or 0
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today      = await db.scalar(select(func.count(Alert.id)).where(Alert.timestamp >= today_start)) or 0
    week_start = datetime.utcnow() - timedelta(days=7)
    this_week  = await db.scalar(select(func.count(Alert.id)).where(Alert.timestamp >= week_start)) or 0

    breakdown_rows = await db.execute(
        select(Alert.crime_type, func.count(Alert.id)).group_by(Alert.crime_type)
    )
    breakdown = {r[0]: r[1] for r in breakdown_rows}

    severity_rows = await db.execute(
        select(Alert.severity, func.count(Alert.id)).group_by(Alert.severity)
    )
    by_severity = {r[0]: r[1] for r in severity_rows}

    # Hourly data for last 24h
    hourly = []
    for h in range(23, -1, -1):
        hour_start = datetime.utcnow().replace(minute=0, second=0, microsecond=0) - timedelta(hours=h)
        hour_end   = hour_start + timedelta(hours=1)
        count = await db.scalar(
            select(func.count(Alert.id)).where(
                and_(Alert.timestamp >= hour_start, Alert.timestamp < hour_end)
            )
        ) or 0
        hourly.append({"hour": hour_start.strftime("%H:00"), "alerts": count})

    return {
        "total_alerts":    total,
        "critical_alerts": critical,
        "high_alerts":     high,
        "today_alerts":    today,
        "this_week":       this_week,
        "unresolved":      unresolved,
        "resolved":        total - unresolved,
        "breakdown":       breakdown,
        "by_severity":     by_severity,
        "hourly_24h":      hourly,
        "active_cameras":  16,
        "active_vehicles": len(DEMO_VEHICLES),
        "system_status":   "operational",
    }

# ── Alerts CRUD ───────────────────────────────────────────────────────────────

@router.get("/api/alerts")
async def get_alerts(
    limit:       int = Query(50, le=500),
    offset:      int = Query(0, ge=0),
    crime_type:  Optional[str] = None,
    severity:    Optional[str] = None,
    resolved:    Optional[bool] = None,
    camera_id:   Optional[str] = None,
    vehicle_id:  Optional[str] = None,
    search:      Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Alert).order_by(desc(Alert.timestamp))
    if crime_type:  query = query.where(Alert.crime_type == crime_type)
    if severity:    query = query.where(Alert.severity == severity)
    if resolved is not None: query = query.where(Alert.resolved == resolved)
    if camera_id:   query = query.where(Alert.camera_id == camera_id)
    if vehicle_id:  query = query.where(Alert.vehicle_id == vehicle_id)
    if search:
        query = query.where(or_(
            Alert.crime_type.contains(search),
            Alert.camera_id.contains(search),
            Alert.notes.contains(search),
        ))
    total_q = select(func.count()).select_from(query.subquery())
    total   = await db.scalar(total_q) or 0
    result  = await db.execute(query.offset(offset).limit(limit))
    alerts  = result.scalars().all()
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "data": [_alert_to_dict(a) for a in alerts],
    }

@router.get("/api/alerts/{alert_id}")
async def get_alert(alert_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert  = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return _alert_to_dict(alert)

@router.post("/api/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: int, body: AlertResolveRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert  = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.resolved    = True
    alert.resolved_at = datetime.utcnow()
    alert.resolved_by = body.resolved_by
    if body.notes:
        alert.notes = body.notes
    await db.commit()
    return {"success": True, "alert_id": alert_id, "resolved_at": alert.resolved_at.isoformat()}

@router.delete("/api/alerts/{alert_id}")
async def delete_alert(alert_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert  = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    await db.delete(alert)
    await db.commit()
    return {"success": True}

def _alert_to_dict(a: Alert) -> dict:
    return {
        "id":            a.id,
        "timestamp":     a.timestamp.isoformat(),
        "crime_type":    a.crime_type,
        "severity":      a.severity,
        "confidence":    a.confidence,
        "latitude":      a.latitude,
        "longitude":     a.longitude,
        "camera_id":     a.camera_id,
        "vehicle_id":    a.vehicle_id,
        "snapshot_path": a.snapshot_path,
        "alert_sent":    a.alert_sent,
        "resolved":      a.resolved,
        "resolved_at":   a.resolved_at.isoformat() if a.resolved_at else None,
        "resolved_by":   a.resolved_by,
        "notes":         a.notes,
        "person_count":  a.person_count,
        "vehicle_count": a.vehicle_count,
        "criminal_name": a.criminal_name,
        "plate_number":  a.plate_number,
        "crowd_risk":    a.crowd_risk,
        "night_mode":    a.night_mode,
    }

# ── Vehicles ──────────────────────────────────────────────────────────────────

@router.get("/api/vehicles")
async def get_vehicles(db: AsyncSession = Depends(get_db)):
    t = datetime.utcnow().timestamp()
    vehicles = []
    for v in DEMO_VEHICLES:
        gps = _gps(v["lat"], v["lng"], t)
        vehicles.append({
            "id":           v["id"],
            "name":         v["name"],
            "status":       "active",
            "lat":          gps["lat"],
            "lng":          gps["lng"],
            "last_seen":    datetime.utcnow().isoformat(),
            "camera_count": 4,
            "officer":      v["officer"],
            "badge":        v["badge"],
            "speed_kmh":    round(random.uniform(0, 60), 1),
            "heading":      round(random.uniform(0, 360), 1),
        })
    return vehicles

@router.get("/api/vehicles/{vehicle_id}/alerts")
async def get_vehicle_alerts(vehicle_id: str, limit: int = 20, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Alert)
        .where(Alert.vehicle_id == vehicle_id)
        .order_by(desc(Alert.timestamp))
        .limit(limit)
    )
    return [_alert_to_dict(a) for a in result.scalars().all()]

# ── Heatmap ───────────────────────────────────────────────────────────────────

@router.get("/api/heatmap-data")
async def get_heatmap_data(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Alert.latitude, Alert.longitude, Alert.crime_type, Alert.severity, Alert.timestamp)
        .where(and_(Alert.latitude.isnot(None), Alert.longitude.isnot(None)))
        .order_by(desc(Alert.timestamp))
        .limit(500)
    )
    points = [
        {"lat": r[0], "lng": r[1], "type": r[2], "severity": r[3],
         "timestamp": r[4].isoformat() if r[4] else None}
        for r in result
    ]
    if not points:
        base_lat, base_lng = 28.6139, 77.2090
        types = ["fight","weapon","accident","suspicious","riot","criminal","stolen_vehicle"]
        sevs  = {"fight":"HIGH","weapon":"CRITICAL","accident":"HIGH",
                 "suspicious":"MEDIUM","riot":"CRITICAL","criminal":"CRITICAL","stolen_vehicle":"HIGH"}
        for _ in range(50):
            ct = random.choice(types)
            points.append({
                "lat":       round(base_lat + random.uniform(-0.07, 0.07), 6),
                "lng":       round(base_lng + random.uniform(-0.07, 0.07), 6),
                "type":      ct,
                "severity":  sevs[ct],
                "timestamp": (datetime.utcnow() - timedelta(hours=random.randint(0,72))).isoformat(),
            })
    return points

# ── Evidence ──────────────────────────────────────────────────────────────────

@router.get("/api/evidence")
async def list_evidence(
    crime_type: Optional[str] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    evidence_dir = Path("evidence")
    evidence_dir.mkdir(exist_ok=True)
    pattern = f"{crime_type}_*.jpg" if crime_type else "*.jpg"
    files = sorted(evidence_dir.glob(pattern), key=lambda f: f.stat().st_mtime, reverse=True)
    result = []
    for f in files[:limit]:
        sha = ""
        try:
            sha = hashlib.sha256(f.read_bytes()).hexdigest()
        except Exception:
            pass
        result.append({
            "filename":   f.name,
            "size_kb":    round(f.stat().st_size / 1024, 1),
            "created":    datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            "crime_type": f.name.split("_")[0],
            "url":        f"/api/evidence/{f.name}",
            "sha256":     sha,
        })
    return result

@router.get("/api/evidence/{filename}")
async def get_evidence_file(filename: str):
    path = Path("evidence") / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(path), media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=3600"})

@router.delete("/api/evidence/{filename}")
async def delete_evidence(filename: str):
    path = Path("evidence") / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    path.unlink()
    return {"success": True}

# ── Video Upload ──────────────────────────────────────────────────────────────

@router.post("/api/upload-video")
async def upload_video(
    file: UploadFile = File(...),
    camera_id: str = Form("CAM-UPLOAD"),
):
    allowed = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"File type {ext} not allowed")
    upload_dir = Path("uploads")
    upload_dir.mkdir(exist_ok=True)
    safe_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
    video_path = upload_dir / safe_name
    content = await file.read()
    with open(video_path, "wb") as f:
        f.write(content)
    size_mb = round(len(content) / 1024 / 1024, 2)
    return {
        "success":   True,
        "filename":  safe_name,
        "path":      str(video_path),
        "size_mb":   size_mb,
        "camera_id": camera_id,
        "ws_url":    f"/ws/video/{camera_id}",
        "message":   "Video uploaded. Connect to ws_url to stream analysis results.",
    }

# ── Criminal Profiles ─────────────────────────────────────────────────────────

@router.get("/api/criminals")
async def list_criminals(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CriminalProfile).where(CriminalProfile.is_active == True).order_by(desc(CriminalProfile.added_at))
    )
    profiles = result.scalars().all()
    return [
        {
            "id":            p.id,
            "name":          p.name,
            "alias":         p.alias,
            "crime_history": p.crime_history,
            "risk_level":    p.risk_level,
            "photo_path":    p.photo_path,
            "added_at":      p.added_at.isoformat(),
            "notes":         p.notes,
        }
        for p in profiles
    ]

@router.post("/api/criminals")
async def add_criminal(
    name:          str = Form(...),
    alias:         str = Form(""),
    crime_history: str = Form(""),
    risk_level:    str = Form("MEDIUM"),
    notes:         str = Form(""),
    image: UploadFile = File(None),
    db: AsyncSession = Depends(get_db),
):
    photo_path = None
    if image and image.filename:
        import cv2, numpy as np
        img_bytes = await image.read()
        img_array = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if img is not None and detector and detector.face_engine:
            photo_path = detector.face_engine.add_criminal_to_db(name, img)
        else:
            db_dir = Path("criminal_db") / name.lower().replace(" ", "_")
            db_dir.mkdir(parents=True, exist_ok=True)
            photo_path = str(db_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
            with open(photo_path, "wb") as f:
                f.write(img_bytes)

    profile = CriminalProfile(
        name=name, alias=alias or None,
        crime_history=crime_history or None,
        risk_level=risk_level,
        photo_path=photo_path,
        notes=notes or None,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return {"success": True, "id": profile.id, "name": profile.name, "photo_path": photo_path}

@router.delete("/api/criminals/{criminal_id}")
async def delete_criminal(criminal_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CriminalProfile).where(CriminalProfile.id == criminal_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile.is_active = False
    await db.commit()
    return {"success": True}

# ── Stolen Vehicles ───────────────────────────────────────────────────────────

@router.get("/api/stolen-vehicles")
async def list_stolen_vehicles(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(StolenVehicle).where(StolenVehicle.is_active == True).order_by(desc(StolenVehicle.reported_at))
    )
    vehicles = result.scalars().all()
    return [
        {
            "id":            v.id,
            "plate_number":  v.plate_number,
            "vehicle_make":  v.vehicle_make,
            "vehicle_model": v.vehicle_model,
            "color":         v.color,
            "status":        v.status,
            "reason":        v.reason,
            "priority":      v.priority,
            "reported_at":   v.reported_at.isoformat(),
            "reported_by":   v.reported_by,
        }
        for v in vehicles
    ]

@router.post("/api/stolen-vehicles")
async def add_stolen_vehicle(
    plate_number:  str = Form(...),
    vehicle_make:  str = Form(""),
    vehicle_model: str = Form(""),
    color:         str = Form(""),
    status:        str = Form("stolen"),
    reason:        str = Form(""),
    priority:      str = Form("HIGH"),
    reported_by:   str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.scalar(
        select(func.count(StolenVehicle.id)).where(StolenVehicle.plate_number == plate_number.upper())
    )
    if existing:
        raise HTTPException(status_code=409, detail="Plate already registered")
    v = StolenVehicle(
        plate_number=plate_number.upper().replace(" ",""),
        vehicle_make=vehicle_make or None,
        vehicle_model=vehicle_model or None,
        color=color or None,
        status=status,
        reason=reason or None,
        priority=priority,
        reported_by=reported_by or None,
    )
    db.add(v)
    await db.commit()
    await db.refresh(v)
    return {"success": True, "id": v.id, "plate_number": v.plate_number}

@router.post("/api/stolen-vehicles/check")
async def check_plate(plate: str = Form(...), db: AsyncSession = Depends(get_db)):
    normalized = plate.upper().replace(" ","").replace("-","")
    result = await db.execute(
        select(StolenVehicle).where(
            and_(StolenVehicle.plate_number == normalized, StolenVehicle.is_active == True)
        )
    )
    v = result.scalar_one_or_none()
    if v:
        return {
            "found":         True,
            "plate_number":  v.plate_number,
            "status":        v.status,
            "priority":      v.priority,
            "reason":        v.reason,
            "vehicle":       f"{v.vehicle_make or ''} {v.vehicle_model or ''}".strip(),
            "color":         v.color,
            "reported_at":   v.reported_at.isoformat(),
        }
    return {"found": False, "plate_number": normalized, "status": "CLEAR"}

@router.delete("/api/stolen-vehicles/{vehicle_id}")
async def remove_stolen_vehicle(vehicle_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(StolenVehicle).where(StolenVehicle.id == vehicle_id))
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=404, detail="Not found")
    v.is_active = False
    await db.commit()
    return {"success": True}

# ── Crime Prediction ──────────────────────────────────────────────────────────

@router.get("/api/predict")
async def predict_crime(
    lat: float = Query(28.6139),
    lng: float = Query(77.2090),
    hour: Optional[int] = None,
    dow:  Optional[int] = None,
):
    global crime_predictor
    if crime_predictor is None:
        from backend.ai.crime_predictor import CrimePredictor
        crime_predictor = CrimePredictor()
    return crime_predictor.predict(lat, lng, hour, dow)

@router.get("/api/predict/heatmap")
async def prediction_heatmap(
    center_lat: float = Query(28.6139),
    center_lng: float = Query(77.2090),
    grid_size:  int   = Query(8, le=15),
):
    global crime_predictor
    if crime_predictor is None:
        from backend.ai.crime_predictor import CrimePredictor
        crime_predictor = CrimePredictor()
    return crime_predictor.generate_city_heatmap(center_lat, center_lng, grid_size)

@router.get("/api/predict/patrol-routes")
async def patrol_routes():
    global crime_predictor
    if crime_predictor is None:
        from backend.ai.crime_predictor import CrimePredictor
        crime_predictor = CrimePredictor()
    vehicles = await get_vehicles()
    return crime_predictor.get_patrol_recommendations(vehicles)

# ── System Logs ───────────────────────────────────────────────────────────────

@router.get("/api/logs")
async def get_logs(limit: int = 100, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SystemLog).order_by(desc(SystemLog.timestamp)).limit(limit)
    )
    logs = result.scalars().all()
    return [
        {"id": l.id, "timestamp": l.timestamp.isoformat(),
         "level": l.level, "module": l.module, "message": l.message}
        for l in logs
    ]

# ── WebSocket: Live Camera ────────────────────────────────────────────────────

@router.websocket("/ws/camera/{camera_id}")
async def ws_camera(websocket: WebSocket, camera_id: str):
    await websocket.accept()
    alert_manager.register_ws_client(websocket)
    cap = None
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            cap = None
            await _stream_demo(websocket, camera_id)
            return
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            result = detector.detect_frame(frame, camera_id)
            if result["is_alert"]:
                t = datetime.utcnow().timestamp()
                gps = _gps(28.6139, 77.2090, t)
                await alert_manager.dispatch(result, gps)
            await websocket.send_json({
                "type":      "frame",
                "camera_id": camera_id,
                "frame":     detector.frame_to_base64(result["annotated_frame"]),
                "detection": _det_summary(result),
            })
            await asyncio.sleep(0.033)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        if cap:
            cap.release()
        alert_manager.unregister_ws_client(websocket)

SCENARIOS = [
    ("normal",         0.0,  "LOW",      30),
    ("suspicious",     0.63, "MEDIUM",   20),
    ("normal",         0.0,  "LOW",      20),
    ("fight",          0.84, "HIGH",     25),
    ("normal",         0.0,  "LOW",      20),
    ("weapon",         0.92, "CRITICAL", 20),
    ("normal",         0.0,  "LOW",      20),
    ("criminal",       0.79, "CRITICAL", 20),
    ("normal",         0.0,  "LOW",      20),
    ("stolen_vehicle", 0.88, "HIGH",     20),
    ("normal",         0.0,  "LOW",      20),
    ("riot",           0.74, "CRITICAL", 25),
    ("normal",         0.0,  "LOW",      30),
]

async def _stream_demo(websocket: WebSocket, camera_id: str):
    sc_idx = 0
    sc_frame = 0
    frame_idx = 0
    try:
        while True:
            crime_type, confidence, severity, duration = SCENARIOS[sc_idx % len(SCENARIOS)]
            sc_frame += 1
            if sc_frame >= duration:
                sc_frame = 0
                sc_idx += 1
            frame = _make_frame(crime_type, camera_id, frame_idx)
            frame_idx += 1
            is_alert = crime_type != "normal"
            await websocket.send_json({
                "type":      "frame",
                "camera_id": camera_id,
                "frame":     detector.frame_to_base64(frame),
                "detection": {
                    "crime_type":   crime_type,
                    "severity":     severity,
                    "confidence":   confidence,
                    "person_count": random.randint(1,4) if is_alert else random.randint(0,2),
                    "vehicle_count":1 if crime_type == "stolen_vehicle" else 0,
                    "is_alert":     is_alert,
                    "timestamp":    datetime.utcnow().isoformat(),
                    "night_mode":   False,
                    "face":  {"has_criminal_match": crime_type == "criminal",
                              "criminal_matches": [{"identity":"Demo Suspect","confidence":0.79}] if crime_type=="criminal" else []},
                    "anpr":  {"has_alert": crime_type == "stolen_vehicle",
                              "alerts": [{"plate_text":"DL01AB1234","check":{"status":"STOLEN"}}] if crime_type=="stolen_vehicle" else []},
                    "crowd": {"riot_risk": 0.74 if crime_type == "riot" else 0.0,
                              "person_count": 15 if crime_type == "riot" else (random.randint(1,3) if is_alert else 0)},
                },
            })
            await asyncio.sleep(1.5)
    except WebSocketDisconnect:
        pass

def _make_frame(crime_type: str, camera_id: str, idx: int) -> np.ndarray:
    import math
    h, w = 480, 640
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[:] = (14, 17, 28)
    for x in range(0, w, 80): cv2.line(frame, (x,0),(x,h),(20,25,40),1)
    for y in range(0, h, 60): cv2.line(frame, (0,y),(w,y),(20,25,40),1)
    t = idx * 0.05
    colors = {"fight":(0,80,255),"weapon":(0,0,255),"suspicious":(0,200,200),
              "riot":(0,0,200),"criminal":(0,0,255),"stolen_vehicle":(0,0,255),"normal":(0,180,0)}
    c = colors.get(crime_type,(0,180,0))
    if crime_type != "normal":
        px = int(200 + 20*math.sin(t))
        py = 280
        cv2.rectangle(frame,(px-30,py-80),(px+30,py+80),c,2)
        cv2.putText(frame,"person 0.91",(px-30,py-85),cv2.FONT_HERSHEY_SIMPLEX,0.45,c,1)
        if crime_type in ("fight","riot"):
            px2 = int(380 + 15*math.sin(t+1))
            cv2.rectangle(frame,(px2-30,py-80),(px2+30,py+80),c,2)
            cv2.putText(frame,"person 0.87",(px2-30,py-85),cv2.FONT_HERSHEY_SIMPLEX,0.45,c,1)
        if crime_type == "weapon":
            cv2.rectangle(frame,(px+30,py),(px+70,py+12),(0,0,255),-1)
            cv2.putText(frame,"knife 0.91",(px+30,py-5),cv2.FONT_HERSHEY_SIMPLEX,0.4,(0,0,255),1)
        if crime_type == "stolen_vehicle":
            cv2.rectangle(frame,(100,200),(540,400),(0,0,255),2)
            cv2.putText(frame,"car 0.94",(100,195),cv2.FONT_HERSHEY_SIMPLEX,0.5,(0,0,255),1)
            cv2.rectangle(frame,(100,370),(540,400),(0,0,0),-1)
            cv2.putText(frame,"DL01AB1234 [STOLEN]",(110,392),cv2.FONT_HERSHEY_SIMPLEX,0.55,(0,0,255),2)
        if crime_type == "criminal":
            cv2.rectangle(frame,(px-30,py-80),(px+30,py-20),(0,0,255),3)
            cv2.putText(frame,"CRIMINAL MATCH",(px-30,py-90),cv2.FONT_HERSHEY_SIMPLEX,0.45,(0,0,255),2)
        sev = {"weapon":"CRITICAL","criminal":"CRITICAL","riot":"CRITICAL",
               "fight":"HIGH","stolen_vehicle":"HIGH","suspicious":"MEDIUM"}.get(crime_type,"MEDIUM")
        bc = {"CRITICAL":(0,0,160),"HIGH":(0,40,160),"MEDIUM":(0,80,130)}.get(sev,(0,80,130))
        cv2.rectangle(frame,(0,0),(w,45),bc,-1)
        cv2.putText(frame,f"  ALERT: {crime_type.upper().replace('_',' ')}  |  {sev}",
                    (8,32),cv2.FONT_HERSHEY_DUPLEX,0.85,(255,255,255),2)
    ts = datetime.now().strftime("%H:%M:%S")
    cv2.putText(frame,f"[{camera_id}]  LIVE  {ts}",(8,h-10),cv2.FONT_HERSHEY_SIMPLEX,0.4,(80,80,80),1)
    return frame

def _det_summary(r: dict) -> dict:
    return {
        "crime_type":   r["crime_type"],
        "severity":     r["severity"],
        "confidence":   r["confidence"],
        "person_count": r["person_count"],
        "vehicle_count":r.get("vehicle_count",0),
        "is_alert":     r["is_alert"],
        "timestamp":    r["timestamp"],
        "night_mode":   r.get("night_mode",False),
        "face":  {"has_criminal_match": r.get("face",{}).get("has_criminal_match",False),
                  "criminal_matches":   r.get("face",{}).get("criminal_matches",[])},
        "anpr":  {"has_alert": r.get("anpr",{}).get("has_alert",False),
                  "alerts":    r.get("anpr",{}).get("alerts",[])},
        "crowd": {"riot_risk":    r.get("crowd",{}).get("riot_risk",0.0),
                  "person_count": r.get("crowd",{}).get("person_count",0)},
    }

# ── WebSocket: Alert Feed ─────────────────────────────────────────────────────

@router.websocket("/ws/alerts")
async def ws_alerts(websocket: WebSocket):
    await websocket.accept()
    alert_manager.register_ws_client(websocket)
    try:
        await websocket.send_json({"type":"connected","message":"CrimeWatch AI alert feed active","timestamp":datetime.utcnow().isoformat()})
        while True:
            await asyncio.sleep(25)
            await websocket.send_json({"type":"ping","timestamp":datetime.utcnow().isoformat()})
    except WebSocketDisconnect:
        alert_manager.unregister_ws_client(websocket)
    except Exception:
        alert_manager.unregister_ws_client(websocket)
