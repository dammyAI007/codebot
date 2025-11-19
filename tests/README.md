# Codebot Test Suite

Comprehensive test suite covering unit, API, and integration testing.

## Quick Start

```bash
# Install dependencies
uv pip install -e ".[test]"

# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=codebot --cov-report=html
```

## Test Organization

- `unit/` - Unit tests for core modules (models, parser, utils, storage, GitHub, Git, Claude)
- `api/` - API endpoint and webhook tests
- `conftest.py` - Shared fixtures and configuration

## Common Commands

```bash
# Run specific category
uv run pytest tests/unit/
uv run pytest tests/api/

# Run specific file
uv run pytest tests/unit/test_models.py

# Run with markers
uv run pytest -m unit
uv run pytest -m "not slow"

# View coverage
open htmlcov/index.html
```

## Key Fixtures (conftest.py)

- `sample_task_prompt` - Sample TaskPrompt instance
- `mock_github_app_auth` - Mocked GitHub authentication
- `temp_workspace` - Temporary workspace directory
- `in_memory_db` - In-memory SQLite database
- `flask_client` - Flask test client

## Writing Tests

```python
def test_example(sample_task_prompt):
    """Tests should be descriptive and follow AAA pattern."""
    # Arrange
    prompt = sample_task_prompt
    
    # Act
    result = process(prompt)
    
    # Assert
    assert result.is_valid
```

Mock external dependencies to keep tests fast and isolated:
```python
def test_with_mock(mocker):
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=0)
    # ... test code
```
