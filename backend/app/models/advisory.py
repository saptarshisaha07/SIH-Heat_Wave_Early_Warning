from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.db.session import Base


class Advisory(Base):
    __tablename__ = "advisories"

    id = Column(Integer, primary_key=True, index=True)
    risk_level = Column(String(50), index=True, nullable=False)  # e.g., Yellow, Orange, Red / High, Extreme
    target_audience = Column(String(100), nullable=False)        # e.g., General Public, Outdoor Workers, Vulnerable Groups
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    precautions = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
