from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base


class AlertLog(Base):
    __tablename__ = "alerts_log"

    id = Column(Integer, primary_key=True, index=True)
    ward_id = Column(Integer, ForeignKey("wards.id", ondelete="SET NULL"), nullable=True, index=True)
    alert_type = Column(String(100), nullable=False)  # e.g., Heat Wave Warning, Extreme Alert
    severity = Column(String(50), nullable=False)     # e.g., Yellow, Orange, Red / High, Extreme
    message = Column(Text, nullable=False)
    issued_at = Column(DateTime, default=datetime.utcnow, index=True)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

    ward = relationship("Ward", back_populates="alerts")
