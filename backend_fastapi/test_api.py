#!/usr/bin/env python3
"""
FastAPI Prediction Testing Script
Test all prediction endpoints without needing curl or Postman
"""

import httpx
import json
import asyncio
from datetime import datetime
from typing import Optional

# Configuration
API_BASE_URL = "http://localhost:8000"
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]

class PredictionAPITester:
    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        self.client = httpx.Client()
    
    def print_header(self, text: str):
        print("\n" + "=" * 70)
        print(f"  {text}")
        print("=" * 70)
    
    def print_result(self, status_code: int, data: dict, endpoint: str):
        if status_code == 200:
            print(f"✅ {endpoint} - Status: {status_code}")
            print(json.dumps(data, indent=2, default=str))
        else:
            print(f"❌ {endpoint} - Status: {status_code}")
            print(json.dumps(data, indent=2, default=str))
    
    def test_health(self):
        """Test API health"""
        self.print_header("1. Test API Health")
        try:
            response = self.client.get(f"{self.base_url}/health")
            self.print_result(response.status_code, response.json(), "GET /health")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def test_symbols(self):
        """Get list of supported symbols"""
        self.print_header("2. Get Supported Symbols")
        try:
            response = self.client.get(f"{self.base_url}/symbols")
            self.print_result(response.status_code, response.json(), "GET /symbols")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def test_single_prediction(self, symbol: str = "BTCUSDT"):
        """Get prediction for a single symbol"""
        self.print_header(f"3. Get Prediction for {symbol}")
        try:
            response = self.client.get(f"{self.base_url}/prediction/{symbol}")
            data = response.json() if response.status_code == 200 else response.json()
            self.print_result(response.status_code, data, f"GET /prediction/{symbol}")
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def test_all_predictions(self):
        """Get all latest predictions"""
        self.print_header("4. Get All Latest Predictions")
        try:
            response = self.client.get(f"{self.base_url}/predictions")
            data = response.json() if response.status_code == 200 else response.json()
            
            if response.status_code == 200:
                # Pretty print predictions table
                print(f"✅ GET /predictions - Status: {response.status_code}")
                print(f"Total predictions: {data.get('count', 0)}\n")
                
                predictions = data.get('predictions', [])
                if predictions:
                    print(f"{'Symbol':<10} | {'Current':<12} | {'Predicted':<12} | {'Change':<8} | Direction | Confidence")
                    print("-" * 90)
                    for pred in predictions:
                        symbol = pred.get('symbol', 'N/A')
                        current = pred.get('current_price', 0)
                        predicted = pred.get('predicted_price', 0)
                        change = pred.get('predicted_change', 0)
                        direction = pred.get('direction', 'N/A')
                        confidence = pred.get('confidence_score', 0)
                        
                        print(f"{symbol:<10} | ${current:>10.2f} | ${predicted:>10.2f} | {change:>6.2f}% | {direction:>9} | {confidence:>10.2%}")
                else:
                    print("No predictions available yet.")
                    print("Run: python Spark/batch/predict_price.py")
            else:
                self.print_result(response.status_code, data, "GET /predictions")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def test_prediction_history(self, symbol: str = "BTCUSDT", limit: int = 5):
        """Get prediction history for a symbol"""
        self.print_header(f"5. Get Prediction History for {symbol} (limit={limit})")
        try:
            response = self.client.get(
                f"{self.base_url}/prediction/{symbol}/history",
                params={"limit": limit}
            )
            data = response.json() if response.status_code == 200 else response.json()
            
            if response.status_code == 200:
                print(f"✅ GET /prediction/{symbol}/history - Status: {response.status_code}")
                print(f"Total history records: {data.get('count', 0)}\n")
                
                history = data.get('predictions', [])
                if history:
                    for i, pred in enumerate(history[:5], 1):
                        pred_time = pred.get('prediction_time', 'N/A')
                        current = pred.get('close', 0)
                        predicted = pred.get('predicted_price', 0)
                        actual = pred.get('actual_price', 'TBD')
                        change = pred.get('predicted_change_pct', 0)
                        direction = pred.get('direction', 'N/A')
                        
                        print(f"Record {i}:")
                        print(f"  Prediction Time: {pred_time}")
                        print(f"  Current Price:   ${current}")
                        print(f"  Predicted Price: ${predicted}")
                        print(f"  Actual Price:    {actual}")
                        print(f"  Expected Change: {change:.4f}%")
                        print(f"  Direction:       {direction}")
                        print()
                else:
                    print("No historical predictions found.")
            else:
                self.print_result(response.status_code, data, f"GET /prediction/{symbol}/history")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def test_ohlc_data(self, symbol: str = "BTCUSDT", interval: str = "5m", limit: int = 5):
        """Get OHLC data for a symbol"""
        self.print_header(f"6. Get OHLC Data for {symbol} ({interval}, limit={limit})")
        try:
            response = self.client.get(
                f"{self.base_url}/ohlc",
                params={
                    "symbol": symbol,
                    "interval": interval,
                    "limit": limit
                }
            )
            data = response.json() if response.status_code == 200 else response.json()
            
            if response.status_code == 200:
                print(f"✅ GET /ohlc - Status: {response.status_code}")
                print(f"Symbol: {data.get('symbol')}, Interval: {data.get('interval')}")
                print(f"Total candles: {data.get('count')}\n")
                
                candles = data.get('candles', [])
                if candles:
                    print(f"{'Time':<20} | {'Open':<10} | {'High':<10} | {'Low':<10} | {'Close':<10} | {'Volume'}")
                    print("-" * 85)
                    for candle in candles[:5]:
                        time_str = candle.get('time', 'N/A')
                        open_price = candle.get('open', 0)
                        high_price = candle.get('high', 0)
                        low_price = candle.get('low', 0)
                        close_price = candle.get('close', 0)
                        volume = candle.get('volume', 0)
                        
                        print(f"{time_str:<20} | ${open_price:>8.2f} | ${high_price:>8.2f} | ${low_price:>8.2f} | ${close_price:>8.2f} | {volume:>10.2f}")
            else:
                self.print_result(response.status_code, data, "GET /ohlc")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def run_all_tests(self):
        """Run all tests"""
        print("\n")
        print("╔" + "=" * 68 + "╗")
        print("║" + " " * 15 + "🔮 FastAPI Prediction Testing" + " " * 23 + "║")
        print("╚" + "=" * 68 + "╝")
        
        # 1. Health check
        self.test_health()
        
        # 2. List symbols
        self.test_symbols()
        
        # 3. Single prediction
        success = self.test_single_prediction("BTCUSDT")
        
        # 4. All predictions
        self.test_all_predictions()
        
        # 5. History
        if success:
            self.test_prediction_history("BTCUSDT")
        
        # 6. OHLC data
        self.test_ohlc_data("BTCUSDT")
        
        print("\n")
        print("╔" + "=" * 68 + "╗")
        print("║" + " " * 20 + "✅ Testing Complete" + " " * 29 + "║")
        print("╚" + "=" * 68 + "╝\n")
        
        print("📌 Key Endpoints:")
        print(f"  • GET {self.base_url}/health              - Check API status")
        print(f"  • GET {self.base_url}/symbols             - Get supported symbols")
        print(f"  • GET {self.base_url}/prediction/BTCUSDT  - Get prediction for symbol")
        print(f"  • GET {self.base_url}/predictions         - Get all predictions")
        print(f"  • GET {self.base_url}/prediction/BTCUSDT/history - Prediction history")
        print(f"  • GET {self.base_url}/ohlc?symbol=BTCUSDT&interval=5m - Get OHLC data\n")
    
    def close(self):
        self.client.close()


if __name__ == "__main__":
    tester = PredictionAPITester()
    try:
        tester.run_all_tests()
    except KeyboardInterrupt:
        print("\n\n⚠️  Testing interrupted by user")
    finally:
        tester.close()
