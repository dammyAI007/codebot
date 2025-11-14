"""Task prompt parser for JSON and YAML formats."""

import json
from pathlib import Path
from typing import Union

import yaml

from codebot.core.models import TaskPrompt


def parse_task_prompt(content: str) -> TaskPrompt:
    """
    Parse task prompt from string content.
    Automatically detects JSON or YAML format.
    
    Args:
        content: String content of the task prompt
        
    Returns:
        TaskPrompt object
    """
    content = content.strip()
    
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # If JSON fails, try YAML
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise ValueError(f"Unable to parse task prompt. Not valid JSON or YAML: {e}")
    
    return TaskPrompt(**data)


def parse_task_prompt_file(file_path: Union[str, Path]) -> TaskPrompt:
    """
    Parse task prompt from a file.
    
    Args:
        file_path: Path to the task prompt file
        
    Returns:
        TaskPrompt object
    """
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Task prompt file not found: {file_path}")
    
    content = path.read_text()
    return parse_task_prompt(content)
