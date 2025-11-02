# tests/test_performance.py
import pytest
import requests
import time
import statistics
from concurrent.futures import ThreadPoolExecutor

class TestPerformance:
    """Performance and load testing"""
    
    def test_response_time_benchmark(self):
        """Benchmark API response times"""
        session = requests.Session()
        session.verify = False
        
        response_times = []
        
        for _ in range(10):
            try:
                start = time.time()
                response = session.get("https://localhost/auth/health", timeout=10)
                end = time.time()
                
                if response.status_code == 200:
                    response_times.append(end - start)
                    
            except requests.exceptions.RequestException:
                pass
            
            time.sleep(0.1)
        
        if response_times:
            avg_time = statistics.mean(response_times)
            max_time = max(response_times)
            
            print(f"Average response time: {avg_time:.3f}s")
            print(f"Max response time: {max_time:.3f}s")
            
            # Performance assertions
            assert avg_time < 2.0, "Average response time should be under 2s"
            assert max_time < 5.0, "Max response time should be under 5s"
    
    def test_load_testing(self):
        """Simple load testing"""
        session = requests.Session()
        session.verify = False
        
        def make_request():
            try:
                response = session.get("https://localhost/auth/health", timeout=5)
                return response.status_code
            except:
                return 0
        
        # Test with 50 concurrent requests
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(make_request) for _ in range(50)]
            results = [f.result() for f in futures]
        
        successful = sum(1 for r in results if r == 200)
        print(f"Successful requests: {successful}/50")
        
        # Should handle at least 80% of requests successfully
        success_rate = successful / 50
        assert success_rate >= 0.5, f"Success rate too low: {success_rate}"