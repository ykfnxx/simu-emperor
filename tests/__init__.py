"""
Interface Test Framework

This project provides two testing solutions:

1. test_runner.py - Self-contained test runner (no pytest required)
   Run: python tests/test_runner.py

2. pytest test suite - More professional testing framework
   Run:
   - Install pytest: pip install pytest
   - Run tests: pytest tests/ -v
   - View coverage: pytest tests/ --cov=core --cov=db --cov-report=html

Recommended to use pytest for continuous development and CI/CD integration,
test_runner.py is suitable for quick verification and constrained environments.
"""
