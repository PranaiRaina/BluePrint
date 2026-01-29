"""
Article Service: Fetches news and runs sentiment analysis.
"""
from transformers import pipeline
import yfinance as yf
from typing import Dict, List, Any
import os

class ArticleService:
    """Service to fetch articles and analyze sentiment using DistilBERT model."""
    
    def __init__(self):
        self.classifier = None
        self.model_path = os.path.join(
            os.path.dirname(__file__), 
            "..", "models", "sentiment_model"
        )
    
    def load_model(self):
        """Lazy load the sentiment model on first use."""
        if self.classifier is None:
            try:
                print(f"[ArticleService] Loading sentiment model from {self.model_path}")
                self.classifier = pipeline(
                    "text-classification",
                    model=self.model_path,
                    tokenizer=self.model_path
                )
                print("[ArticleService] Model loaded successfully")
            except Exception as e:
                print(f"[ArticleService] Failed to load custom model: {e}. Using fallback.")
                self.classifier = pipeline("sentiment-analysis")
    
    def _map_label(self, label: str) -> str:
        """Map model labels to Positive/Negative/Neutral."""
        if label in ["NEGATIVE", "LABEL_0"]:
            return "Negative"
        elif label in ["POSITIVE", "LABEL_2", "LABEL_1"]:
            # Note: LABEL_1 could be neutral in some models, adjust if needed
            if label == "LABEL_1":
                return "Neutral"
            return "Positive"
        else:
            return "Neutral"
    
    def _extract_link(self, item: dict) -> str:
        """Extract article link from yfinance news item."""
        content = item.get("content", {})
        link_data = content.get("clickThroughUrl") or content.get("canonicalUrl")
        
        if isinstance(link_data, dict):
            return link_data.get("url", "#")
        return link_data or "#"
    
    async def fetch_and_analyze(self, ticker: str, max_articles: int = 20) -> Dict[str, Any]:
        """
        Fetch news articles for a ticker and analyze sentiment.
        
        Args:
            ticker: Stock ticker symbol (e.g., "AAPL")
            max_articles: Maximum number of articles to fetch
            
        Returns:
            Dict with overall_sentiment, articles list, and counts
        """
        self.load_model()
        
        results: List[Dict] = []
        sentiment_counts = {"Positive": 0, "Negative": 0, "Neutral": 0}
        
        try:
            stock = yf.Ticker(ticker.upper())
            news = stock.news[:max_articles] if stock.news else []
            
            for item in news:
                content = item.get("content", {})
                headline = content.get("title", "")
                
                if not headline:
                    continue
                
                # Run sentiment classifier
                try:
                    result = self.classifier(headline[:512])[0]
                    sentiment = self._map_label(result["label"])
                except Exception as e:
                    print(f"[ArticleService] Classification error: {e}")
                    sentiment = "Neutral"
                
                sentiment_counts[sentiment] += 1
                
                results.append({
                    "title": headline,
                    "link": self._extract_link(item),
                    "sentiment": sentiment,
                    "score": result.get("score", 0) if 'result' in dir() else 0
                })
            
            # Determine overall sentiment
            if sentiment_counts["Positive"] > sentiment_counts["Negative"]:
                overall = "Bullish"
            elif sentiment_counts["Negative"] > sentiment_counts["Positive"]:
                overall = "Bearish"
            else:
                overall = "Neutral"
            
            return {
                "ticker": ticker.upper(),
                "overall_sentiment": overall,
                "articles": results,
                "counts": sentiment_counts
            }
            
        except Exception as e:
            print(f"[ArticleService] Error fetching articles: {e}")
            return {
                "ticker": ticker.upper(),
                "overall_sentiment": "Unknown",
                "articles": [],
                "counts": sentiment_counts,
                "error": str(e)
            }

# Singleton instance
article_service = ArticleService()
