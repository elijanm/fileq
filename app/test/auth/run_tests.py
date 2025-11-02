# run_tests.py - Test runner script

#!/usr/bin/env python3

import sys
import subprocess
import argparse
import os
from pathlib import Path

def run_command(cmd, description):
    """Run a command and handle errors"""
    print(f"\n🔄 {description}")
    print(f"Command: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"✅ {description} - SUCCESS")
        if result.stdout:
            print(result.stdout)
    else:
        print(f"❌ {description} - FAILED")
        if result.stderr:
            print(result.stderr)
        return False
    
    return True

def main():
    parser = argparse.ArgumentParser(description="Run authentication API tests")
    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument("--integration", action="store_true", help="Run integration tests only")
    parser.add_argument("--security", action="store_true", help="Run security tests only")
    parser.add_argument("--performance", action="store_true", help="Run performance tests only")
    parser.add_argument("--coverage", action="store_true", help="Generate coverage report")
    parser.add_argument("--parallel", "-n", type=int, help="Run tests in parallel")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--setup", action="store_true", help="Setup test environment only")
    parser.add_argument("--cleanup", action="store_true", help="Cleanup test environment")
    
    args = parser.parse_args()
    
    # Base pytest command
    pytest_cmd = ["python", "-m", "pytest"]
    
    if args.verbose:
        pytest_cmd.append("-v")
    
    if args.parallel:
        pytest_cmd.extend(["-n", str(args.parallel)])
    
    if args.coverage:
        pytest_cmd.extend([
            "--cov=main",
            "--cov-report=html",
            "--cov-report=term-missing"
        ])
    
    # Setup test environment
    if args.setup or not any([args.unit, args.integration, args.security, args.performance]):
        print("🔧 Setting up test environment...")
        
        # Check if Docker is available
        if not run_command(["docker", "--version"], "Checking Docker"):
            print("❌ Docker is required for testing")
            return 1
        
        # Build test environment
        if not run_command(
            ["docker-compose", "-f", "docker-compose.test.yml", "build"],
            "Building test containers"
        ):
            return 1
        
        if args.setup:
            print("✅ Test environment setup complete")
            return 0
    
    # Cleanup
    if args.cleanup:
        print("🧹 Cleaning up test environment...")
        run_command(
            ["docker-compose", "-f", "docker-compose.test.yml", "down", "-v"],
            "Cleaning up test containers"
        )
        return 0
    
    # Run specific test types
    success = True
    
    if args.unit or not any([args.integration, args.security, args.performance]):
        print("\n🧪 Running unit tests...")
        cmd = pytest_cmd + ["-m", "unit", "test_auth_api.py"]
        success &= run_command(cmd, "Unit tests")
    
    if args.integration:
        print("\n🔗 Running integration tests...")
        cmd = pytest_cmd + ["-m", "integration", "test_integration.py"]
        success &= run_command(cmd, "Integration tests")
    
    if args.security:
        print("\n🛡️ Running security tests...")
        cmd = pytest_cmd + ["-m", "security"]
        success &= run_command(cmd, "Security tests")
    
    if args.performance:
        print("\n⚡ Running performance tests...")
        cmd = pytest_cmd + ["-m", "performance", "--benchmark-only"]
        success &= run_command(cmd, "Performance tests")
    
    # Generate test report
    if success and args.coverage:
        print("\n📊 Generating test coverage report...")
        print("Coverage report available at: htmlcov/index.html")
    
    # Summary
    if success:
        print("\n🎉 All tests passed successfully!")
        return 0
    else:
        print("\n💥 Some tests failed. Check the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
