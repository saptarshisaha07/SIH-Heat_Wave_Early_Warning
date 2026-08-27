from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.orm import relationship
from app.db.session import Base


class Ward(Base):
    __tablename__ = "wards"

    id = Column(Integer, primary_key=True, index=True)
    ward_number = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(150), index=True, nullable=False)
    zone = Column(String(100), nullable=True)
    population = Column(Integer, nullable=True)
    area_sq_km = Column(Float, nullable=True)
    vulnerability_index = Column(Float, nullable=False, default=0.0)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships to other models
    weather_readings = relationship("WeatherReading", back_populates="ward", cascade="all, delete-orphan")
    risk_scores = relationship("RiskScore", back_populates="ward", cascade="all, delete-orphan")
    forecasts = relationship("Forecast", back_populates="ward", cascade="all, delete-orphan")
    alerts = relationship("AlertLog", back_populates="ward", cascade="all, delete-orphan")
