"""
CrimeWatch AI — Database Models
Full production schema with proper relationships and indexes
"""

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text, Boolean,
    Index, ForeignKey, Enum as SAEnum
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
import enum
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./crimewatch.db")

engine = create_async_engine(DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


class SeverityLevel(str, enum.Enum):
    LOW      = "LOW"
    MEDIUM   = "MEDIUM"
    HIGH     = "HIGH"
    CRITICAL = "CRITICAL"


class CrimeType(str, enum.Enum):
    FIGHT           = "fight"
    WEAPON          = "weapon"
    ACCIDENT        = "accident"
    SUSPICIOUS      = "suspicious"
    RIOT            = "riot"
    CRIMINAL        = "criminal"
    STOLEN_VEHICLE  = "stolen_vehicle"
    LOITERING       = "loitering"
    NORMAL          = "normal"


class Alert(Base):
    __tablename__ = "alerts"

    id              = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp       = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    crime_type      = Column(String(50), nullable=False, index=True)
    confidence      = Column(Float, nullable=False, default=0.0)
    severity        = Column(String(20), nullable=False, index=True)
    latitude        = Column(Float, nullable=True)
    longitude       = Column(Float, nullable=True)
    camera_id       = Column(String(50), nullable=False, index=True)
    vehicle_id      = Column(String(50), nullable=True)
    snapshot_path   = Column(String(500), nullable=True)
    video_clip_path = Column(String(500), nullable=True)
    alert_sent      = Column(Boolean, default=False)
    resolved        = Column(Boolean, default=False, index=True)
    resolved_at     = Column(DateTime, nullable=True)
    resolved_by     = Column(String(100), nullable=True)
    notes           = Column(Text, nullable=True)
    person_count    = Column(Integer, default=0)
    vehicle_count   = Column(Integer, default=0)
    # Extra detection info
    criminal_name   = Column(String(200), nullable=True)
    plate_number    = Column(String(50), nullable=True)
    crowd_risk      = Column(Float, default=0.0)
    night_mode      = Column(Boolean, default=False)

    __table_args__ = (
        Index("ix_alerts_timestamp_severity", "timestamp", "severity"),
        Index("ix_alerts_crime_resolved", "crime_type", "resolved"),
    )


class Vehicle(Base):
    __tablename__ = "vehicles"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id   = Column(String(50), unique=True, index=True, nullable=False)
    name         = Column(String(100), nullable=False)
    status       = Column(String(20), default="active")
    latitude     = Column(Float, nullable=True)
    longitude    = Column(Float, nullable=True)
    last_seen    = Column(DateTime, default=datetime.utcnow)
    camera_count = Column(Integer, default=4)
    officer_name = Column(String(100), nullable=True)
    badge_number = Column(String(50), nullable=True)


class EvidenceLog(Base):
    __tablename__ = "evidence_logs"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    alert_id    = Column(Integer, ForeignKey("alerts.id"), nullable=True, index=True)
    file_path   = Column(String(500), nullable=False)
    file_type   = Column(String(20), default="image")
    created_at  = Column(DateTime, default=datetime.utcnow)
    hash_sha256 = Column(String(64), nullable=True)
    file_size   = Column(Integer, nullable=True)


class CriminalProfile(Base):
    __tablename__ = "criminal_profiles"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    name        = Column(String(200), nullable=False, index=True)
    alias       = Column(String(200), nullable=True)
    crime_history = Column(Text, nullable=True)
    risk_level  = Column(String(20), default="MEDIUM")
    photo_path  = Column(String(500), nullable=True)
    added_at    = Column(DateTime, default=datetime.utcnow)
    is_active   = Column(Boolean, default=True)
    notes       = Column(Text, nullable=True)


class StolenVehicle(Base):
    __tablename__ = "stolen_vehicles"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    plate_number = Column(String(50), unique=True, index=True, nullable=False)
    vehicle_make = Column(String(100), nullable=True)
    vehicle_model= Column(String(100), nullable=True)
    color        = Column(String(50), nullable=True)
    status       = Column(String(20), default="stolen")  # stolen, wanted, recovered
    reason       = Column(String(200), nullable=True)
    priority     = Column(String(20), default="HIGH")
    reported_at  = Column(DateTime, default=datetime.utcnow)
    reported_by  = Column(String(100), nullable=True)
    is_active    = Column(Boolean, default=True)


class SystemLog(Base):
    __tablename__ = "system_logs"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    timestamp  = Column(DateTime, default=datetime.utcnow, index=True)
    level      = Column(String(20), default="INFO")
    module     = Column(String(100), nullable=True)
    message    = Column(Text, nullable=False)
    camera_id  = Column(String(50), nullable=True)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
