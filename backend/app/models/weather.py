from datetime import datetime
from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base


class WeatherReading(Base):
    __tablename__ = "weather_readings"

    id = Column(Integer, primary_key=True, index=True)
    ward_id = Column(Integer, ForeignKey("wards.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime, index=True, nullable=False)
    temperature = Column(Float, nullable=False)  # in Celsius
    relative_humidity = Column(Float, nullable=False)  # in %
    wind_speed = Column(Float, nullable=True)  # in m/s
    solar_radiation = Column(Float, nullable=True)  # in W/m2
    heat_index = Column(Float, nullable=True)
    wet_bulb_temp = Column(Float, nullable=True)
    apparent_temp = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    ward = relationship("Ward", back_populates="weather_readings")
