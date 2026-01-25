from sqlalchemy import Column, String, Boolean, Integer, Enum
from db.session import Base
import enum

class RiskTolerance(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean(), default=True)
    is_superuser = Column(Boolean(), default=False)
    
    # User Settings (Encrypted or Configured)
    # Stored as encrypted strings using core.security.encrypt_data
    alpha_vantage_key = Column(String, nullable=True) 
    wolfram_app_id = Column(String, nullable=True)
    
    # enum mapped to string in DB for simplicity or generic Enum
    risk_tolerance = Column(String, default=RiskTolerance.MEDIUM.value) 
