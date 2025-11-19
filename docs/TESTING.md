# Testing Guide

Complete testing documentation for the Moderator Console project.

## Table of Contents

- [Overview](#overview)
- [Testing Strategy](#testing-strategy)
- [Test Structure](#test-structure)
- [Running Tests](#running-tests)
- [Test Coverage](#test-coverage)
- [Writing Tests](#writing-tests)
- [CI/CD Integration](#cicd-integration)
- [Performance Benchmarks](#performance-benchmarks)
- [Troubleshooting](#troubleshooting)

## Overview

The project uses **pytest** as the testing framework with comprehensive test coverage across:

- **Unit Tests**: Individual component testing
- **Integration Tests**: Component interaction testing
- **End-to-End Tests**: Complete workflow testing
- **Performance Tests**: Benchmarking and load testing
- **Security Tests**: Security measure validation

### Test Statistics

- **Total Test Files**: 20+
- **Total Tests**: 200+
- **Target Coverage**: 90%+
- **Test Execution Time**: < 10 seconds

## Testing Strategy

### Test Pyramid

```
                  /\
                 /  \
               /  E2E  \
              /----------\
             /Integration \
            /--------------\
           /   Unit Tests   \
          /------------------\
```

1. **Unit Tests (60%)**: Fast, isolated tests for individual functions/classes
2. **Integration Tests (30%)**: Test component interactions
3. **End-to-End Tests (10%)**: Complete workflow validation

### Test Categories

#### 1. Unit Tests

Located in `tests/test_*.py`, these test individual components:

- **DAO Tests** (`test_dao.py`): Database access layer
- **Service Tests** (`test_*.py`): Business logic
- **Handler Tests** (`test_*_handlers.py`): Event handlers

#### 2. Integration Tests

Test component interactions:

- **Edit Integration** (`test_edit_integration.py`)
- **Multiserver Integration** (`test_multiserver_integration.py`)
- **LLM Integration** (`test_llm.py`)

#### 3. End-to-End Tests

Complete workflow tests in `test_end_to_end.py`:

- Discord message → Task → LLM → Telegram → Reply → Posted
- Multi-server workflows
- Search and export workflows
- Error recovery scenarios

#### 4. Performance Tests

Benchmarking in `test_performance.py`:

- Database query performance
- LLM response time
- Concurrent operations
- Memory usage
- Throughput testing

#### 5. Security Tests

Security validation in `test_security.py`:

- SQL injection prevention
- XSS prevention
- Authentication/authorization
- Input validation
- Secrets management

## Test Structure

### Directory Layout

```
tests/
├── __init__.py
├── conftest.py                    # Shared fixtures
├── test_end_to_end.py            # E2E tests (17 tests)
├── test_performance.py           # Performance tests (12 tests)
├── test_security.py              # Security tests (14 tests)
├── test_dao.py                   # DAO unit tests
├── test_integration.py           # Integration tests
├── test_multiserver_*.py         # Multi-server tests
├── test_search.py                # Search functionality
├── test_edit_*.py                # Edit feature tests
├── test_confirmations.py         # Confirmation flows
├── test_help_system.py           # Help system
├── test_llm*.py                  # LLM service tests
├── test_worker.py                # Worker tests
└── test_*.py                     # Other test modules
```

### Test File Naming

- `test_*.py`: Test files must start with `test_`
- `*_test.py`: Alternative naming (also valid)
- Test functions: Must start with `test_`
- Test classes: Must start with `Test`

## Running Tests

### Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt

# Install test dependencies
pip install pytest pytest-asyncio pytest-cov pytest-mock psutil
```

### Basic Test Execution

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_end_to_end.py

# Run specific test
pytest tests/test_end_to_end.py::test_complete_message_workflow

# Run tests matching pattern
pytest -k "test_security"
```

### Advanced Options

```bash
# Run with coverage report
pytest --cov=backend/src --cov-report=html

# Run only failed tests from last run
pytest --lf

# Run tests in parallel (requires pytest-xdist)
pytest -n auto

# Run with detailed output
pytest -vv --tb=short

# Run with warnings
pytest -W error

# Stop on first failure
pytest -x

# Run specific markers
pytest -m "asyncio"
```

### Test Markers

Use markers to categorize tests:

```python
@pytest.mark.asyncio       # Async tests
@pytest.mark.slow          # Slow tests
@pytest.mark.integration   # Integration tests
@pytest.mark.security      # Security tests
@pytest.mark.performance   # Performance tests
```

Run specific markers:

```bash
# Run only async tests
pytest -m asyncio

# Run everything except slow tests
pytest -m "not slow"

# Run security and performance tests
pytest -m "security or performance"
```

## Test Coverage

### Coverage Goals

- **Overall**: 90%+ code coverage
- **Critical Paths**: 100% coverage
- **DAOs**: 100% coverage
- **Services**: 95%+ coverage
- **Handlers**: 90%+ coverage

### Generating Coverage Reports

```bash
# Generate HTML coverage report
pytest --cov=backend/src --cov-report=html

# Open report in browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux

# Generate terminal report
pytest --cov=backend/src --cov-report=term

# Generate XML report (for CI)
pytest --cov=backend/src --cov-report=xml
```

### Coverage Report Interpretation

```
Name                                 Stmts   Miss  Cover
--------------------------------------------------------
backend/src/database/dao/message_dao.py   120      5    96%
backend/src/services/llm.py               150     10    93%
backend/src/telegram/handlers.py          200     15    93%
--------------------------------------------------------
TOTAL                                    5000    250    95%
```

- **Stmts**: Total statements
- **Miss**: Uncovered statements
- **Cover**: Coverage percentage

## Writing Tests

### Test Structure

Follow the **Arrange-Act-Assert** pattern:

```python
@pytest.mark.asyncio
async def test_example(mock_db_connection):
    # Arrange: Set up test data and mocks
    conn = mock_db_connection
    test_data = {'id': 1, 'name': 'test'}

    # Act: Execute the functionality
    result = await some_function(conn, test_data)

    # Assert: Verify the results
    assert result is not None
    assert result['id'] == 1
```

### Using Fixtures

```python
def test_with_fixtures(
    mock_db_connection,
    mock_telegram_bot,
    sample_message_data
):
    """Test using multiple fixtures."""
    # Fixtures are automatically injected
    assert mock_db_connection is not None
    assert sample_message_data['platform'] == 'discord'
```

### Mocking

```python
from unittest.mock import Mock, MagicMock, patch

@pytest.mark.asyncio
async def test_with_mocking():
    # Mock a function
    with patch('database.dao.MessageDAO.create_message') as mock_create:
        mock_create.return_value = 1

        result = await mock_create(conn, **message_data)

        assert result == 1
        mock_create.assert_called_once()
```

### Async Tests

```python
@pytest.mark.asyncio
async def test_async_function():
    """Test async functions."""
    result = await some_async_function()
    assert result is not None
```

### Parametrized Tests

```python
@pytest.mark.parametrize("input,expected", [
    ("hello", "HELLO"),
    ("world", "WORLD"),
    ("test", "TEST"),
])
def test_uppercase(input, expected):
    """Test with multiple inputs."""
    assert input.upper() == expected
```

### Exception Testing

```python
def test_exception_handling():
    """Test that exceptions are raised."""
    with pytest.raises(ValueError):
        raise ValueError("Test error")

    with pytest.raises(ValueError, match="specific message"):
        raise ValueError("specific message")
```

### Test Data Generators

Use the `test_data_generator` fixture:

```python
def test_with_generated_data(test_data_generator):
    """Test with generated data."""
    # Generate multiple messages
    messages = test_data_generator.generate_messages(count=10)
    assert len(messages) == 10

    # Generate users
    users = test_data_generator.generate_users(count=5)
    assert len(users) == 5
```

## CI/CD Integration

### GitHub Actions

Example workflow (`.github/workflows/tests.yml`):

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v2

      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov

      - name: Run tests
        run: |
          pytest --cov=backend/src --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v2
        with:
          file: ./coverage.xml
```

### Pre-commit Hooks

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest
        language: system
        pass_filenames: false
        always_run: true
```

## Performance Benchmarks

### Baseline Performance Metrics

| Operation | Target | Acceptable | Notes |
|-----------|--------|------------|-------|
| Simple DB Query | < 100ms | < 200ms | SELECT with WHERE |
| Complex DB Query | < 500ms | < 1s | Joins, aggregations |
| LLM Response | < 5s | < 10s | With retry |
| API Health Check | < 200ms | < 500ms | Status endpoint |
| Message Processing | < 1s | < 2s | End-to-end |
| Bulk Insert (100) | < 1s | < 2s | Batch operations |
| Search Query | < 500ms | < 1s | Full-text search |
| Cache Read | < 50ms | < 100ms | Redis GET |

### Running Performance Tests

```bash
# Run performance tests only
pytest tests/test_performance.py -v

# Run with benchmark output
pytest tests/test_performance.py --benchmark

# Generate performance report
pytest tests/test_performance.py --benchmark-autosave
```

### Performance Test Guidelines

1. **Use realistic data volumes**: Test with production-like dataset sizes
2. **Measure consistently**: Use the `performance_timer` fixture
3. **Set clear baselines**: Define expected performance ranges
4. **Test concurrency**: Verify parallel operation handling
5. **Monitor memory**: Check for memory leaks

## Troubleshooting

### Common Issues

#### 1. Import Errors

```
ModuleNotFoundError: No module named 'database'
```

**Solution**: Check `sys.path` in `conftest.py`:

```python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'src'))
```

#### 2. Async Test Failures

```
RuntimeError: Event loop is closed
```

**Solution**: Use `@pytest.mark.asyncio` decorator:

```python
@pytest.mark.asyncio
async def test_async_function():
    ...
```

#### 3. Database Connection Issues

```
Database not available: Connection refused
```

**Solution**: Tests use mocks by default. For real DB tests:

```python
@pytest.mark.skipif(not DB_AVAILABLE, reason="Database not available")
async def test_with_real_db():
    ...
```

#### 4. Fixture Not Found

```
fixture 'mock_db_connection' not found
```

**Solution**: Ensure fixture is defined in `conftest.py` or imported

#### 5. Coverage Not Collected

```bash
# Ensure coverage package is installed
pip install pytest-cov

# Specify source directory
pytest --cov=backend/src
```

### Debug Mode

Run tests in debug mode:

```bash
# Enable debug output
pytest -vv --log-cli-level=DEBUG

# Drop into debugger on failure
pytest --pdb

# Drop into debugger on error
pytest --pdbcls=IPython.terminal.debugger:TerminalPdb
```

### Test Isolation

Ensure tests are independent:

```python
@pytest.fixture(autouse=True)
def reset_state():
    """Reset global state before each test."""
    # Clear caches
    cache.clear()

    yield

    # Cleanup after test
    cleanup()
```

## Best Practices

### DO

✅ Write descriptive test names
✅ Use fixtures for reusable test data
✅ Mock external dependencies
✅ Test edge cases and error conditions
✅ Keep tests fast (< 1s per test)
✅ Use parametrize for similar test cases
✅ Document complex test scenarios
✅ Maintain test independence

### DON'T

❌ Don't test implementation details
❌ Don't use sleep() for timing
❌ Don't share state between tests
❌ Don't skip tests without good reason
❌ Don't write tests that depend on order
❌ Don't test external APIs directly
❌ Don't commit failing tests

## Test Maintenance

### Regular Tasks

1. **Weekly**: Review test coverage, fix failures
2. **Monthly**: Update performance baselines
3. **Per Release**: Run full test suite with real services
4. **Continuous**: Fix flaky tests immediately

### Updating Tests

When changing code:

1. Update affected tests
2. Add tests for new functionality
3. Remove tests for deleted functionality
4. Verify coverage doesn't decrease

### Test Refactoring

Signs tests need refactoring:

- High duplication
- Slow execution
- Frequent failures
- Hard to understand
- Difficult to maintain

## Resources

### Documentation

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html)

### Internal

- [Project README](/README.md)
- [Development Setup](/SETUP.md)
- [API Documentation](/docs/API.md)

## Summary

This comprehensive testing suite ensures:

- **Quality**: 90%+ code coverage
- **Reliability**: All critical paths tested
- **Performance**: Benchmarked and monitored
- **Security**: Validated security measures
- **Maintainability**: Clear, documented tests

For questions or issues, refer to the troubleshooting section or contact the development team.
