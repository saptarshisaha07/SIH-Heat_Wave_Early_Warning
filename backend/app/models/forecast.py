from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base


class Forecast(Base):
    __tablename__ = "forecasts"

    id = Column(Integer, primary_key=True, index=True)
    ward_id = Column(Integer, ForeignKey("wards.id", ondelete="CASCADE"), nullable=False, index=True)
    forecast_time = Column(DateTime, index=True, nullable=False)  # Time when forecast was issued
    target_time = Column(DateTime, index=True, nullable=False)    # Future target timestamp
    predicted_temp = Column(Float, nullable=False)
    predicted_humidity = Column(Float, nullable=True)
    predicted_heat_index = Column(Float, nullable=True)
    predicted_risk_level = Column(String(50), nullable=True)
    confidence_score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    ward = relationship("Ward", back_populates="forecasts")
