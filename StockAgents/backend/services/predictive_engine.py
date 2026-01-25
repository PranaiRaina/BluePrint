import numpy as np
from sklearn.ensemble import RandomForestRegressor
import pandas as pd

class PredictiveEngine:
    def __init__(self):
        self.model = RandomForestRegressor(n_estimators=100)
        self.is_trained = False

    def train(self, historical_data: list[dict]):
        """
        Train the model on historical data.
        Expected format: List of dicts with 'close', 'open', 'volume', etc.
        """
        df = pd.DataFrame(historical_data)
        if df.empty:
            return
            
        # Feature Engineering (Basic)
        df['return'] = df['close'].pct_change()
        df['volatility'] = df['return'].rolling(window=5).std()
        df.dropna(inplace=True)
        
        features = ['open', 'volume', 'volatility']
        target = 'close' # Predicting next close price (simplified)
        
        X = df[features]
        y = df[target]
        
        self.model.fit(X, y)
        self.is_trained = True

    def predict_next(self, current_data: dict) -> float:
        """Predict next closing price."""
        if not self.is_trained:
            # Return dummy prediction or fallback
            return current_data.get('close', 0) * 1.01
            
        input_df = pd.DataFrame([current_data])
        # Note: In real app, we need consistent feature engineering here
        # This is simplified
        return self.model.predict(input_df)[0]

predictive_engine = PredictiveEngine()
