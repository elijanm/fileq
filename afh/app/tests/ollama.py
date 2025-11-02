import mlflow
import requests
import time
import json
import numpy as np
from datetime import datetime
from typing import List, Dict, Any
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import tempfile

# Configuration
OLLAMA_BASE_URL = "http://95.110.228.29:8201/v1"
MLFLOW_TRACKING_URI = "http://95.110.228.29:5100"

# Set MLflow tracking URI and use local artifact storage
mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

# Create local directory for artifacts
ARTIFACTS_DIR = os.path.join(os.getcwd(), "benchmark_artifacts")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

class OllamaBenchmark:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.models = self.get_available_models()
        self.artifacts_dir = ARTIFACTS_DIR
        
    def get_available_models(self) -> List[str]:
        """Fetch available models from Ollama"""
        try:
            response = requests.get(f"{self.base_url}/models")
            response.raise_for_status()
            data = response.json()
            return [model['id'] for model in data.get('data', [])]
        except Exception as e:
            print(f"Error fetching models: {e}")
            return []
    
    def generate_completion(self, model: str, prompt: str, max_tokens: int = 512, timeout: int = 180) -> Dict[str, Any]:
        """Generate completion and measure performance"""
        url = f"{self.base_url}/chat/completions"
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.7
        }
        
        start_time = time.time()
        
        try:
            response = requests.post(url, json=payload, timeout=timeout)
            response.raise_for_status()
            end_time = time.time()
            
            result = response.json()
            
            # Extract metrics
            completion_text = result['choices'][0]['message']['content']
            tokens_generated = result.get('usage', {}).get('completion_tokens', 0)
            total_tokens = result.get('usage', {}).get('total_tokens', 0)
            latency = end_time - start_time
            tokens_per_second = tokens_generated / latency if latency > 0 else 0
            
            return {
                'success': True,
                'completion': completion_text,
                'latency': latency,
                'tokens_generated': tokens_generated,
                'total_tokens': total_tokens,
                'tokens_per_second': tokens_per_second,
                'error': None
            }
        except Exception as e:
            end_time = time.time()
            return {
                'success': False,
                'completion': None,
                'latency': end_time - start_time,
                'tokens_generated': 0,
                'total_tokens': 0,
                'tokens_per_second': 0,
                'error': str(e)
            }
    
    def evaluate_accuracy(self, model: str, test_cases: List[Dict[str, Any]]) -> Dict[str, float]:
        """Evaluate model accuracy on test cases"""
        correct = 0
        total = len(test_cases)
        
        for case in test_cases:
            result = self.generate_completion(model, case['prompt'], max_tokens=100)
            if result['success']:
                # Simple accuracy check (can be customized)
                if case['expected_answer'].lower() in result['completion'].lower():
                    correct += 1
        
        return {
            'accuracy': correct / total if total > 0 else 0,
            'correct': correct,
            'total': total
        }
    
    def run_benchmark(self, test_prompts: List[str], accuracy_tests: List[Dict[str, Any]] = None):
        """Run comprehensive benchmark for all models"""
        
        print(f"Found {len(self.models)} models: {', '.join(self.models)}")
        print("=" * 80)
        
        # Try to create experiment, if it fails, just use default
        try:
            mlflow.set_experiment("ollama-model-benchmark")
        except Exception as e:
            print(f"Note: Using default experiment - {e}")
        
        all_results = []
        
        for model in self.models:
            print(f"\nBenchmarking model: {model}")
            print("-" * 80)
            
            run_name = f"{model}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            try:
                with mlflow.start_run(run_name=run_name):
                    # Log model parameters
                    mlflow.log_param("model_name", model)
                    mlflow.log_param("num_test_prompts", len(test_prompts))
                    
                    # Speed benchmark
                    latencies = []
                    tokens_per_sec = []
                    total_tokens_list = []
                    
                    for idx, prompt in enumerate(test_prompts):
                        print(f"  Test {idx + 1}/{len(test_prompts)}: ", end="", flush=True)
                        result = self.generate_completion(model, prompt)
                        
                        if result['success']:
                            latencies.append(result['latency'])
                            tokens_per_sec.append(result['tokens_per_second'])
                            total_tokens_list.append(result['tokens_generated'])
                            print(f"✓ ({result['latency']:.2f}s, {result['tokens_per_second']:.2f} tok/s)")
                            
                            # Log intermediate results
                            try:
                                mlflow.log_metric(f"test_{idx+1}_latency", result['latency'], step=idx)
                                mlflow.log_metric(f"test_{idx+1}_tokens_per_sec", result['tokens_per_second'], step=idx)
                            except Exception as e:
                                print(f"    Warning: Could not log metric - {e}")
                        else:
                            print(f"✗ Error: {result['error']}")
                    
                    # Calculate statistics
                    if latencies:
                        avg_latency = np.mean(latencies)
                        std_latency = np.std(latencies)
                        avg_tokens_per_sec = np.mean(tokens_per_sec)
                        avg_tokens_generated = np.mean(total_tokens_list)
                        
                        # Log metrics to MLflow
                        try:
                            mlflow.log_metric("avg_latency", avg_latency)
                            mlflow.log_metric("std_latency", std_latency)
                            mlflow.log_metric("min_latency", min(latencies))
                            mlflow.log_metric("max_latency", max(latencies))
                            mlflow.log_metric("avg_tokens_per_second", avg_tokens_per_sec)
                            mlflow.log_metric("avg_tokens_generated", avg_tokens_generated)
                        except Exception as e:
                            print(f"  Warning: Could not log metrics - {e}")
                        
                        print(f"\n  Speed Metrics:")
                        print(f"    Avg Latency: {avg_latency:.2f}s (±{std_latency:.2f}s)")
                        print(f"    Avg Speed: {avg_tokens_per_sec:.2f} tokens/sec")
                        print(f"    Avg Tokens: {avg_tokens_generated:.0f}")
                        
                        # Accuracy benchmark (if provided)
                        if accuracy_tests:
                            print(f"\n  Running accuracy tests...")
                            accuracy_result = self.evaluate_accuracy(model, accuracy_tests)
                            try:
                                mlflow.log_metric("accuracy", accuracy_result['accuracy'])
                                mlflow.log_metric("correct_answers", accuracy_result['correct'])
                            except Exception as e:
                                print(f"    Warning: Could not log accuracy - {e}")
                            
                            print(f"    Accuracy: {accuracy_result['accuracy']:.2%} ({accuracy_result['correct']}/{accuracy_result['total']})")
                        
                        # Store results
                        model_result = {
                            'model': model,
                            'avg_latency': avg_latency,
                            'std_latency': std_latency,
                            'avg_tokens_per_sec': avg_tokens_per_sec,
                            'avg_tokens_generated': avg_tokens_generated
                        }
                        
                        if accuracy_tests:
                            model_result['accuracy'] = accuracy_result['accuracy']
                        
                        all_results.append(model_result)
                        
                        # Create and save visualizations locally
                        self.create_visualizations(model, latencies, tokens_per_sec, run_name)
                        
                    else:
                        print(f"  No successful completions for {model}")
                        
            except Exception as e:
                print(f"  Error during MLflow logging for {model}: {e}")
                print(f"  Continuing benchmark without MLflow tracking...")
                
                # Continue benchmark even if MLflow fails
                latencies = []
                tokens_per_sec = []
                total_tokens_list = []
                
                for idx, prompt in enumerate(test_prompts):
                    print(f"  Test {idx + 1}/{len(test_prompts)}: ", end="", flush=True)
                    result = self.generate_completion(model, prompt)
                    
                    if result['success']:
                        latencies.append(result['latency'])
                        tokens_per_sec.append(result['tokens_per_second'])
                        total_tokens_list.append(result['tokens_generated'])
                        print(f"✓ ({result['latency']:.2f}s, {result['tokens_per_second']:.2f} tok/s)")
                    else:
                        print(f"✗ Error: {result['error']}")
                
                if latencies:
                    model_result = {
                        'model': model,
                        'avg_latency': np.mean(latencies),
                        'std_latency': np.std(latencies),
                        'avg_tokens_per_sec': np.mean(tokens_per_sec),
                        'avg_tokens_generated': np.mean(total_tokens_list)
                    }
                    all_results.append(model_result)
        
        # Create comparison plots
        if all_results:
            self.create_comparison_plots(all_results)
        
        return all_results
    
    def create_visualizations(self, model_name: str, latencies: List[float], tokens_per_sec: List[float], run_name: str):
        """Create and save visualization artifacts locally"""
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        
        # Latency distribution
        axes[0].hist(latencies, bins=20, color='skyblue', edgecolor='black', alpha=0.7)
        axes[0].set_title(f'{model_name} - Latency Distribution')
        axes[0].set_xlabel('Latency (seconds)')
        axes[0].set_ylabel('Frequency')
        axes[0].axvline(np.mean(latencies), color='red', linestyle='--', label=f'Mean: {np.mean(latencies):.2f}s')
        axes[0].legend()
        
        # Tokens per second
        axes[1].hist(tokens_per_sec, bins=20, color='lightgreen', edgecolor='black', alpha=0.7)
        axes[1].set_title(f'{model_name} - Tokens per Second')
        axes[1].set_xlabel('Tokens/Second')
        axes[1].set_ylabel('Frequency')
        axes[1].axvline(np.mean(tokens_per_sec), color='red', linestyle='--', label=f'Mean: {np.mean(tokens_per_sec):.2f}')
        axes[1].legend()
        
        plt.tight_layout()
        
        # Save locally
        filename = os.path.join(self.artifacts_dir, f"{model_name.replace(':', '_')}_{run_name}_performance.png")
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        print(f"  Saved visualization: {filename}")
        
        # Try to log to MLflow
        try:
            mlflow.log_artifact(filename)
            print(f"  Logged to MLflow")
        except Exception as e:
            print(f"  Warning: Could not log artifact to MLflow - {e}")
        
        plt.close()
    
    def create_comparison_plots(self, results: List[Dict[str, Any]]):
        """Create comparison plots across all models"""
        df = pd.DataFrame(results)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        
        # Latency comparison
        axes[0, 0].barh(df['model'], df['avg_latency'], color='skyblue', edgecolor='black')
        axes[0, 0].set_xlabel('Average Latency (seconds)')
        axes[0, 0].set_title('Model Latency Comparison')
        axes[0, 0].invert_yaxis()
        
        # Tokens per second comparison
        axes[0, 1].barh(df['model'], df['avg_tokens_per_sec'], color='lightgreen', edgecolor='black')
        axes[0, 1].set_xlabel('Tokens per Second')
        axes[0, 1].set_title('Model Speed Comparison')
        axes[0, 1].invert_yaxis()
        
        # Tokens generated
        axes[1, 0].barh(df['model'], df['avg_tokens_generated'], color='lightcoral', edgecolor='black')
        axes[1, 0].set_xlabel('Average Tokens Generated')
        axes[1, 0].set_title('Model Output Length')
        axes[1, 0].invert_yaxis()
        
        # Accuracy (if available)
        if 'accuracy' in df.columns:
            axes[1, 1].barh(df['model'], df['accuracy'] * 100, color='gold', edgecolor='black')
            axes[1, 1].set_xlabel('Accuracy (%)')
            axes[1, 1].set_title('Model Accuracy Comparison')
            axes[1, 1].invert_yaxis()
        else:
            axes[1, 1].text(0.5, 0.5, 'No accuracy data', ha='center', va='center')
            axes[1, 1].set_title('Model Accuracy Comparison')
        
        plt.tight_layout()
        
        # Save locally
        comparison_filename = os.path.join(self.artifacts_dir, f"model_comparison_{timestamp}.png")
        plt.savefig(comparison_filename, dpi=150, bbox_inches='tight')
        print(f"\nSaved comparison chart: {comparison_filename}")
        
        plt.close()
        
        # Save results as CSV
        csv_filename = os.path.join(self.artifacts_dir, f"benchmark_results_{timestamp}.csv")
        df.to_csv(csv_filename, index=False)
        print(f"Saved results CSV: {csv_filename}")
        
        # Try to log to MLflow
        try:
            with mlflow.start_run(run_name=f"comparison_{timestamp}"):
                mlflow.log_artifact(comparison_filename)
                mlflow.log_artifact(csv_filename)
                
                mlflow.log_metric("fastest_model_tokens_per_sec", df['avg_tokens_per_sec'].max())
                mlflow.log_metric("lowest_latency", df['avg_latency'].min())
                
                print("Logged comparison to MLflow")
        except Exception as e:
            print(f"Warning: Could not log comparison to MLflow - {e}")
        
        print("\n" + "=" * 80)
        print("BENCHMARK SUMMARY")
        print("=" * 80)
        print(df.to_string(index=False))
        print("=" * 80)
        print(f"\nAll artifacts saved to: {self.artifacts_dir}")


# Example usage
if __name__ == "__main__":
    # Initialize benchmark
    benchmark = OllamaBenchmark(OLLAMA_BASE_URL)
    
    # Define test prompts for speed testing
    test_prompts = [
        "Explain quantum computing in simple terms.",
        "Write a short poem about artificial intelligence.",
        "What are the main differences between Python and JavaScript?",
        "Describe the process of photosynthesis.",
        "Write a function to calculate the fibonacci sequence in Python.",
        "Explain the concept of machine learning to a beginner.",
        "What are the benefits of renewable energy?",
        "Describe the water cycle in detail."
    ]
    
    # Define accuracy test cases (optional)
    accuracy_tests = [
        {
            "prompt": "What is 2 + 2?",
            "expected_answer": "4"
        },
        {
            "prompt": "What is the capital of France?",
            "expected_answer": "Paris"
        },
        {
            "prompt": "Who wrote Romeo and Juliet?",
            "expected_answer": "Shakespeare"
        },
        {
            "prompt": "What is the largest planet in our solar system?",
            "expected_answer": "Jupiter"
        },
        {
            "prompt": "What is H2O commonly known as?",
            "expected_answer": "water"
        }
    ]
    
    # Run benchmark
    print("Starting Ollama Model Benchmark")
    print("=" * 80)
    results = benchmark.run_benchmark(test_prompts, accuracy_tests)
    
    print("\n" + "=" * 80)
    print("Benchmark complete!")
    print(f"Results saved to: {ARTIFACTS_DIR}")
    print(f"MLflow UI: {MLFLOW_TRACKING_URI}")
    print("=" * 80)