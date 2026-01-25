from sqlalchemy import Column, String, Float, DateTime, Integer, Index
from db.session import Base
from datetime import datetime

class StockPrice(Base):
    __tablename__ = "stock_prices"

    time = Column(DateTime(timezone=True), primary_key=True, index=True)
    symbol = Column(String, primary_key=True, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Integer)
    
    # TimescaleDB requires the primary key to include the time column
    # __table_args__ = (
    #     Index('ix_stock_prices_time_symbol', 'time', 'symbol'),
    # )

# Note: migration script should run: 
# SELECT create_hypertable('stock_prices', 'time');
