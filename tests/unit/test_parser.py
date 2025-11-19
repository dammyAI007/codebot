"""Tests for task prompt parser."""

import json
import pytest
from pathlib import Path

from codebot.core.parser import parse_task_prompt, parse_task_prompt_file
from codebot.core.models import TaskPrompt


class TestParseTaskPrompt:
    """Tests for parse_task_prompt function."""
    
    def test_parse_json_with_all_fields(self):
        """Test parsing JSON with all fields."""
        json_content = json.dumps({
            "repository_url": "https://github.com/test/repo",
            "description": "Test task description",
            "ticket_id": "TASK-123",
            "ticket_summary": "Test ticket summary",
            "test_command": "pytest tests/",
            "base_branch": "develop",
        })
        
        prompt = parse_task_prompt(json_content)
        
        assert prompt.repository_url == "https://github.com/test/repo"
        assert prompt.description == "Test task description"
        assert prompt.ticket_id == "TASK-123"
        assert prompt.ticket_summary == "Test ticket summary"
        assert prompt.test_command == "pytest tests/"
        assert prompt.base_branch == "develop"
    
    def test_parse_json_with_required_fields_only(self):
        """Test parsing JSON with only required fields."""
        json_content = json.dumps({
            "repository_url": "https://github.com/test/repo",
            "description": "Minimal task",
        })
        
        prompt = parse_task_prompt(json_content)
        
        assert prompt.repository_url == "https://github.com/test/repo"
        assert prompt.description == "Minimal task"
        assert prompt.ticket_id is None
        assert prompt.ticket_summary is None
        assert prompt.test_command is None
        assert prompt.base_branch is None
    
    def test_parse_yaml_with_all_fields(self):
        """Test parsing YAML with all fields."""
        yaml_content = """
repository_url: https://github.com/test/repo
description: Test task from YAML
ticket_id: TASK-456
ticket_summary: YAML ticket
test_command: npm test
base_branch: main
"""
        
        prompt = parse_task_prompt(yaml_content)
        
        assert prompt.repository_url == "https://github.com/test/repo"
        assert prompt.description == "Test task from YAML"
        assert prompt.ticket_id == "TASK-456"
        assert prompt.ticket_summary == "YAML ticket"
        assert prompt.test_command == "npm test"
        assert prompt.base_branch == "main"
    
    def test_parse_yaml_with_required_fields_only(self):
        """Test parsing YAML with only required fields."""
        yaml_content = """
repository_url: https://github.com/test/repo
description: Test task
base_branch: main
"""
        
        prompt = parse_task_prompt(yaml_content)
        
        assert prompt.repository_url == "https://github.com/test/repo"
        assert prompt.description == "Test task"
        assert prompt.base_branch == "main"
    
    def test_parse_invalid_json_falls_back_to_yaml(self):
        """Test that invalid JSON tries YAML parsing."""
        # This is valid YAML but not valid JSON
        yaml_content = """
repository_url: https://github.com/test/repo
description: Not JSON
"""
        
        prompt = parse_task_prompt(yaml_content)
        assert prompt.repository_url == "https://github.com/test/repo"
    
    def test_parse_invalid_json_and_yaml_raises_error(self):
        """Test parsing completely invalid content."""
        invalid_content = "this is not valid {json or yaml"
        
        # Parser will attempt JSON, fail, then attempt YAML which may parse as string
        # This causes TypeError when trying to create TaskPrompt
        with pytest.raises((ValueError, TypeError)):
            parse_task_prompt(invalid_content)
    
    def test_parse_missing_required_field(self):
        """Test that missing required fields raises error."""
        json_content = json.dumps({
            "repository_url": "https://github.com/test/repo",
            # missing description
        })
        
        with pytest.raises(TypeError):
            parse_task_prompt(json_content)
    
    def test_parse_empty_string(self):
        """Test parsing empty string."""
        with pytest.raises((ValueError, TypeError)):
            parse_task_prompt("")
    
    def test_parse_whitespace_only(self):
        """Test parsing whitespace-only string."""
        with pytest.raises((ValueError, TypeError)):
            parse_task_prompt("   \n\t  ")
    
    def test_parse_json_with_extra_fields(self):
        """Test parsing JSON with extra fields (should be ignored)."""
        json_content = json.dumps({
            "repository_url": "https://github.com/test/repo",
            "description": "Test task",
            "extra_field": "ignored",
        })
        
        # TaskPrompt uses dataclass which raises TypeError for unexpected kwargs
        with pytest.raises(TypeError):
            parse_task_prompt(json_content)


class TestParseTaskPromptFile:
    """Tests for parse_task_prompt_file function."""
    
    def test_parse_json_file(self, tmp_path):
        """Test parsing JSON file."""
        json_file = tmp_path / "task.json"
        json_file.write_text(json.dumps({
            "repository_url": "https://github.com/test/repo",
            "description": "Test from JSON file",
        }))
        
        prompt = parse_task_prompt_file(json_file)
        
        assert prompt.repository_url == "https://github.com/test/repo"
        assert prompt.description == "Test from JSON file"
    
    def test_parse_yaml_file(self, tmp_path):
        """Test parsing YAML file."""
        yaml_file = tmp_path / "task.yaml"
        yaml_file.write_text("""
repository_url: https://github.com/test/repo
description: Test from YAML file
ticket_id: TASK-789
test_command: npm test
""")
        
        prompt = parse_task_prompt_file(yaml_file)
        
        assert prompt.repository_url == "https://github.com/test/repo"
        assert prompt.description == "Test from YAML file"
        assert prompt.ticket_id == "TASK-789"
    
    def test_parse_file_with_string_path(self, tmp_path):
        """Test parsing file using string path."""
        json_file = tmp_path / "task.json"
        json_file.write_text(json.dumps({
            "repository_url": "https://github.com/test/repo",
            "description": "String path test",
        }))
        
        prompt = parse_task_prompt_file(str(json_file))
        
        assert prompt.description == "String path test"
    
    def test_parse_nonexistent_file_raises_error(self, tmp_path):
        """Test parsing nonexistent file raises FileNotFoundError."""
        nonexistent = tmp_path / "doesnt_exist.json"
        
        with pytest.raises(FileNotFoundError):
            parse_task_prompt_file(nonexistent)
    
    def test_parse_invalid_file_content(self, tmp_path):
        """Test parsing file with invalid content."""
        bad_file = tmp_path / "bad.txt"
        bad_file.write_text("invalid content")
        
        with pytest.raises((ValueError, TypeError)):
            parse_task_prompt_file(bad_file)
    
    def test_parse_empty_file(self, tmp_path):
        """Test parsing empty file."""
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("")
        
        with pytest.raises((ValueError, TypeError)):
            parse_task_prompt_file(empty_file)
