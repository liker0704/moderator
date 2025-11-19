# Contributing to Discord-Telegram Moderator Console

Thank you for your interest in contributing to this project! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Style Guidelines](#code-style-guidelines)
- [Testing Requirements](#testing-requirements)
- [Pull Request Process](#pull-request-process)
- [Commit Message Conventions](#commit-message-conventions)
- [Project Structure](#project-structure)
- [Reporting Issues](#reporting-issues)

---

## Code of Conduct

This project is a personal/private tool for a single moderator. While contributions are welcome, please:

- Be respectful and constructive in all communications
- Focus on technical merit and code quality
- Understand this is a single-user system (no multi-user features)
- Respect the privacy and security aspects of the system

---

## Getting Started

### Prerequisites

Before you begin, ensure you have:

- **Git** for version control
- **Docker** and **Docker Compose** for containerization
- **Python 3.11+** (if developing without Docker)
- Basic understanding of Discord Gateway and Telegram Bot APIs
- Familiarity with asyncio and asynchronous Python programming

### Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/your-username/moderator.git
   cd moderator
   ```
3. Add upstream remote:
   ```bash
   git remote add upstream https://github.com/original-org/moderator.git
   ```

---

## Development Setup

### Option 1: Docker Development (Recommended)

```bash
# Copy environment file
cp .env.example .env
nano .env  # Fill in your tokens and keys

# Start services with volume mounting for development
docker compose up -d

# View logs
docker compose logs -f backend

# The backend/src/ directory is mounted, so code changes are reflected immediately
```

### Option 2: Local Python Development

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt

# Set environment variables
export $(cat .env | xargs)

# Run application
python backend/src/main.py
```

### Database Setup

```bash
# Database is initialized automatically on first run
# Migrations are applied from migrations/ directory

# To manually run migrations:
docker exec -i moderator_db psql -U moderator -d moderator_db < migrations/001_initial_schema.sql
```

---

## Code Style Guidelines

### Python Style

We follow **PEP 8** with some project-specific conventions:

#### General Principles

- **Line length**: Maximum 100 characters (not 79)
- **Indentation**: 4 spaces (no tabs)
- **Quotes**: Double quotes for strings, single quotes for dict keys when appropriate
- **Imports**: Organized in three groups (standard library, third-party, local)

#### Example

```python
"""
Module docstring explaining the module's purpose.

This should be comprehensive and include usage examples if applicable.
"""

import asyncio
import logging
from typing import Optional, List

import aiohttp
from telegram import Bot

from backend.src.database.dao import MessageDAO
from backend.src.utils.logger import get_logger

logger = get_logger(__name__)


class MyService:
    """
    Brief one-line description of the class.

    Detailed explanation of what this class does,
    its responsibilities, and usage patterns.
    """

    def __init__(self, config: Config):
        """Initialize the service with configuration."""
        self.config = config
        self._client = None

    async def process_message(self, message: Message) -> bool:
        """
        Process a message and return success status.

        Args:
            message: The message to process

        Returns:
            bool: True if processing succeeded, False otherwise

        Raises:
            ValueError: If message is invalid
            ConnectionError: If network operation fails
        """
        logger.info(f"Processing message {message.id}")

        # Implementation here
        return True
```

### Type Hints

- **Always use type hints** for function parameters and return values
- Use `Optional[Type]` for nullable values
- Use `List[Type]`, `Dict[str, Type]` for collections
- Use `from __future__ import annotations` for forward references

### Docstrings

- Use **Google-style docstrings**
- Document all public functions, classes, and modules
- Include `Args`, `Returns`, `Raises` sections
- Provide usage examples for complex functions

### Error Handling

```python
# Use specific exceptions
try:
    result = await api_call()
except aiohttp.ClientError as e:
    logger.error(f"API call failed: {e}")
    raise ConnectionError(f"Failed to connect: {e}") from e
except ValueError as e:
    logger.warning(f"Invalid data: {e}")
    return None

# Use context managers for resources
async with pool.acquire() as conn:
    await conn.execute(query)
```

### Logging

```python
# Import logger
from backend.src.utils.logger import get_logger
logger = get_logger(__name__)

# Use appropriate log levels
logger.debug("Detailed debugging information")
logger.info("General information about normal operation")
logger.warning("Warning about potential issues")
logger.error("Error that needs attention")
logger.critical("Critical error requiring immediate action")

# Include context in log messages
logger.info(f"Processing task {task_id} for user {user_id}")
```

---

## Testing Requirements

### Running Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=backend/src --cov-report=html --cov-report=term

# Run specific test file
pytest tests/test_llm.py -v

# Run specific test
pytest tests/test_llm.py::test_openai_request_format -v
```

### Writing Tests

#### Unit Tests

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.src.services.llm import OpenAIClient


@pytest.mark.asyncio
async def test_openai_generates_response():
    """Test that OpenAI client can generate a response."""
    # Arrange
    client = OpenAIClient(api_key="test-key")
    context = "User: Hello\nAssistant: Hi there!"

    # Mock the HTTP request
    mock_response = {
        "choices": [
            {"message": {"content": "Test response"}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5}
    }

    # Act
    with patch('aiohttp.ClientSession.post') as mock_post:
        mock_post.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
        variants = await client.generate_response(context, num_variants=1)

    # Assert
    assert len(variants) == 1
    assert variants[0]["text"] == "Test response"
    assert variants[0]["confidence"] == 0.9  # finish_reason=stop
```

#### Integration Tests

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_message_flow(test_db):
    """Test complete message ingestion and task creation."""
    # This test requires a real database
    # Marked with @pytest.mark.integration to skip in CI

    # Setup
    dao = MessageDAO(test_db)

    # Test
    message = await dao.create_message(...)
    assert message.id is not None
```

### Test Coverage Requirements

- **Minimum coverage**: 80% for new code
- **Critical paths**: 95%+ coverage (LLM, database operations, posting)
- **Integration tests**: Document setup requirements clearly
- **Mock external services**: Never make real API calls in tests

---

## Pull Request Process

### Before Submitting

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/my-feature-name
   ```

2. **Make your changes**:
   - Follow code style guidelines
   - Add tests for new functionality
   - Update documentation as needed

3. **Run tests**:
   ```bash
   pytest tests/ --cov=backend/src
   ```

4. **Run linting**:
   ```bash
   # Install linters if not already installed
   pip install flake8 black

   # Format code
   black backend/src/

   # Check style
   flake8 backend/src/ --max-line-length=100
   ```

5. **Update documentation**:
   - Update relevant .md files in docs/
   - Update docstrings
   - Add entries to CHANGELOG.md if significant

### Submitting the PR

1. **Push to your fork**:
   ```bash
   git push origin feature/my-feature-name
   ```

2. **Create Pull Request** on GitHub with:
   - **Clear title**: "Add feature X" or "Fix bug in Y"
   - **Description** including:
     - What changes were made and why
     - Related issue numbers (if any)
     - Testing performed
     - Screenshots (if UI changes)
   - **Checklist**:
     ```markdown
     - [ ] Tests pass locally
     - [ ] Code follows style guidelines
     - [ ] Documentation updated
     - [ ] CHANGELOG.md updated (if applicable)
     - [ ] No breaking changes (or documented)
     ```

3. **Respond to review feedback**:
   - Address all comments
   - Push additional commits to the same branch
   - Re-request review when ready

### PR Review Criteria

Your PR will be reviewed for:

- ✅ **Code quality**: Clean, readable, well-structured
- ✅ **Tests**: Adequate coverage and quality
- ✅ **Documentation**: Clear and complete
- ✅ **Functionality**: Works as intended
- ✅ **No regressions**: Doesn't break existing features
- ✅ **Security**: No security vulnerabilities introduced

---

## Commit Message Conventions

We follow a simplified **Conventional Commits** format:

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring (no functionality change)
- `test`: Adding or updating tests
- `chore`: Maintenance tasks (dependencies, config)

### Examples

```
feat(llm): add support for Claude 3.5 Sonnet model

- Add new model to LLMConfig
- Update pricing table for cost calculation
- Add tests for new model

Closes #123
```

```
fix(discord): resolve reconnection loop on gateway disconnect

The gateway was not properly handling RESUME opcode, causing
infinite reconnection attempts. This adds proper session ID
validation and implements exponential backoff.

Fixes #456
```

```
docs(readme): update installation instructions for v1.0

- Add Docker installation steps
- Update environment variable examples
- Add troubleshooting section
```

### Best Practices

- **Use imperative mood**: "Add feature" not "Added feature"
- **Be specific**: "Fix rate limiter bug" not "Fix bug"
- **Reference issues**: Include issue numbers when applicable
- **Keep first line under 72 characters**
- **Separate subject and body with blank line**
- **Explain "why" in body**, not "what" (code shows "what")

---

## Project Structure

Understanding the codebase structure:

```
moderator/
├── backend/
│   ├── src/
│   │   ├── api/                  # HTTP API (health, metrics)
│   │   │   ├── __init__.py
│   │   │   ├── server.py         # aiohttp server
│   │   │   └── health.py         # Health check endpoint
│   │   ├── database/             # Database layer
│   │   │   ├── connection.py     # Connection pooling
│   │   │   ├── models.py         # ORM models
│   │   │   ├── encryption.py     # Token encryption
│   │   │   └── dao/              # Data Access Objects
│   │   ├── discord/              # Discord integration
│   │   │   ├── gateway.py        # WebSocket Gateway client
│   │   │   ├── poster.py         # Message posting
│   │   │   └── api_client.py     # REST API client
│   │   ├── telegram/             # Telegram bot
│   │   │   ├── bot.py            # Bot initialization
│   │   │   ├── handlers.py       # Command and callback handlers
│   │   │   ├── cards.py          # Message card formatting
│   │   │   └── help_content.py   # Help system content
│   │   ├── services/             # Business logic
│   │   │   ├── llm.py            # LLM integration
│   │   │   ├── rate_limiter.py   # Discord rate limiting
│   │   │   ├── reminders.py      # Reminder service
│   │   │   ├── search.py         # Search functionality
│   │   │   ├── stats.py          # Statistics
│   │   │   └── export.py         # Data export
│   │   ├── job_queue/            # Redis queue system
│   │   │   ├── client.py         # Redis client
│   │   │   ├── worker.py         # ARQ worker
│   │   │   └── handlers.py       # Task handlers
│   │   ├── utils/                # Utilities
│   │   │   ├── logger.py         # Logging setup
│   │   │   └── errors.py         # Error handling
│   │   ├── config.py             # Configuration
│   │   └── main.py               # Application entry point
│   └── requirements.txt
├── migrations/                    # Database migrations
│   ├── 001_initial_schema.sql
│   ├── 002_llm_features.sql
│   └── ...
├── tests/                         # Test suite
│   ├── conftest.py               # Pytest fixtures
│   ├── test_llm.py               # LLM tests
│   ├── test_dao.py               # DAO tests
│   └── ...
├── docs/                          # Documentation
│   ├── ARCHITECTURE.md
│   ├── API.md
│   ├── USER_GUIDE.md
│   └── ...
├── docker-compose.yml
├── .env.example
└── README.md
```

### Key Components

- **`main.py`**: Application orchestrator, manages component lifecycle
- **`discord/gateway.py`**: Discord WebSocket connection and event handling
- **`telegram/handlers.py`**: All Telegram commands and callbacks
- **`services/`**: Reusable business logic modules
- **`database/dao/`**: Database operations abstraction

---

## Reporting Issues

### Bug Reports

When reporting a bug, include:

1. **Environment**:
   - OS and version
   - Docker version
   - Python version (if relevant)
   - Project version/commit hash

2. **Steps to reproduce**:
   - Clear, numbered steps
   - Expected behavior
   - Actual behavior

3. **Logs**:
   - Relevant log output (sanitize tokens!)
   - Error messages
   - Stack traces

4. **Configuration** (sanitized):
   - Relevant environment variables (hide sensitive values)
   - Command used to start the application

### Feature Requests

For new features:

1. **Use case**: Explain why this feature is needed
2. **Proposed solution**: Describe how it should work
3. **Alternatives considered**: What other approaches were considered?
4. **Impact**: Will this affect existing functionality?

---

## Development Workflow

### Typical Development Cycle

1. **Create issue** for the feature/bug
2. **Create branch** from main:
   ```bash
   git checkout -b feature/issue-123-add-feature
   ```
3. **Develop** with tests
4. **Test locally**:
   ```bash
   pytest tests/ -v
   docker compose build backend
   docker compose up -d
   # Manual testing
   ```
5. **Commit** with good messages
6. **Push** and create PR
7. **Address** review feedback
8. **Merge** after approval

### Keeping Your Fork Updated

```bash
# Fetch upstream changes
git fetch upstream

# Merge into your main branch
git checkout main
git merge upstream/main

# Update your feature branch
git checkout feature/my-feature
git rebase main
```

---

## Security

### Reporting Security Issues

**DO NOT** open public issues for security vulnerabilities.

Instead, email the maintainer directly with:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Security Best Practices

When contributing:

- **Never commit secrets** (tokens, keys, passwords)
- **Sanitize logs** before sharing
- **Validate all input** from external sources
- **Use parameterized queries** for database operations
- **Follow principle of least privilege**

---

## Questions?

- **Documentation**: Check docs/ directory
- **Existing Issues**: Search GitHub issues
- **Code Examples**: Look at existing implementation
- **Tests**: Check tests/ for usage examples

---

## Thank You!

Thank you for contributing to this project. Your efforts help make this tool better for the moderation workflow it supports.
