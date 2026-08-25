from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base


class RiskScore(Base):
    __tablename__ = "risk_scores"

    id = Column(Integer, primary_key=True, index=True)
    ward_id = Column(Integer, ForeignKey("wards.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime, index=True, nullable=False)
    hazard_score = Column(Float, nullable=False)
    exposure_score = Column(Float, nullable=False)
    vulnerability_score = Column(Float, nullable=False)
    risk_score = Column(Float, nullable=False)
    risk_level = Column(String(50), nullable=False)  # Normal, Watch, Warning, Alert
    created_at = Column(DateTime, default=datetime.utcnow)

    ward = relationship("Ward", back_populates="risk_scores")
