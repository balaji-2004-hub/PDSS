from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Generator

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "supply_chain.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vendor_code: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    metrics: Mapped[list["VendorMetric"]] = relationship("VendorMetric", back_populates="vendor", cascade="all, delete-orphan")
    predictions: Mapped[list["Prediction"]] = relationship("Prediction", back_populates="vendor", cascade="all, delete-orphan")
    forecasts: Mapped[list["Forecast"]] = relationship("Forecast", back_populates="vendor", cascade="all, delete-orphan")
    risk_scores: Mapped[list["RiskScore"]] = relationship("RiskScore", back_populates="vendor", cascade="all, delete-orphan")


class VendorMetric(Base):
    __tablename__ = "vendor_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), index=True)

    reliability_index: Mapped[float] = mapped_column(Float)
    delay_frequency: Mapped[float] = mapped_column(Float)
    rolling_delay_average: Mapped[float] = mapped_column(Float)
    cost_volatility: Mapped[float] = mapped_column(Float)
    quality_weighted_score: Mapped[float] = mapped_column(Float)
    demand_variability_score: Mapped[float] = mapped_column(Float)
    quality_risk: Mapped[float] = mapped_column(Float)
    external_risk_proxy: Mapped[float] = mapped_column(Float)

    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="metrics")


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vendor_id: Mapped[int | None] = mapped_column(ForeignKey("vendors.id"), nullable=True, index=True)

    model_type: Mapped[str] = mapped_column(String(64), index=True)
    input_payload: Mapped[dict] = mapped_column(JSON)
    predicted_label: Mapped[str] = mapped_column(String(128))
    predicted_probability: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="predictions")


class Forecast(Base):
    __tablename__ = "forecasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), index=True)

    forecast_month: Mapped[date] = mapped_column(Date, index=True)
    predicted_cost: Mapped[float] = mapped_column(Float)
    lower_bound: Mapped[float] = mapped_column(Float)
    upper_bound: Mapped[float] = mapped_column(Float)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="forecasts")


class RiskScore(Base):
    __tablename__ = "risk_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), index=True)

    score: Mapped[float] = mapped_column(Float, index=True)
    delay_probability: Mapped[float] = mapped_column(Float)
    quality_risk: Mapped[float] = mapped_column(Float)
    cost_volatility: Mapped[float] = mapped_column(Float)
    external_risk_proxy: Mapped[float] = mapped_column(Float)
    demand_variability: Mapped[float] = mapped_column(Float)

    risk_level: Mapped[str] = mapped_column(String(32), index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="risk_scores")


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()