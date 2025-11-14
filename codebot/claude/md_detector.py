"""CLAUDE.md detection and handling."""

from pathlib import Path
from typing import Optional


def detect_claude_md(repo_path: Path) -> Optional[Path]:
    """
    Detect if CLAUDE.md or Agents.md exists in the repository.
    
    Args:
        repo_path: Path to the repository root
        
    Returns:
        Path to CLAUDE.md if found, None otherwise
    """
    claude_md_path = repo_path / "CLAUDE.md"
    if claude_md_path.exists():
        return claude_md_path
    
    agents_md_path = repo_path / "Agents.md"
    if agents_md_path.exists():
        return agents_md_path
    
    return None


def check_claude_md_exists(repo_path: Path) -> bool:
    return detect_claude_md(repo_path) is not None


def get_claude_md_warning(repo_path: Path) -> Optional[str]:
    """
    Get a warning message if CLAUDE.md doesn't exist.
    
    Args:
        repo_path: Path to the repository root
        
    Returns:
        Warning message if CLAUDE.md is missing, None otherwise
    """
    if not check_claude_md_exists(repo_path):
        return (
            "WARNING: No CLAUDE.md or Agents.md found in repository. "
            "Consider creating one with test commands, environment setup, "
            "and coding guidelines for better results."
        )
    return None
