from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base


class AlertLog(Base):
    __tablename__ = "alerts_log"

    id = Column(Integer, primary_key=True, index=True)
    ward_id = Column(Integer, ForeignKey("wards.id", ondelete="SET NULL"), nullable=True, index=True)
    channel = Column(String(50), nullable=False, default="sms")
    message = Column(Text, nullable=False)
    status = Column(String(50), nullable=False, default="simulated")
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    ward = relationship("Ward", back_populates="alerts")
