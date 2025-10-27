"""Utility functions for codebot."""

import hashlib
import uuid
from typing import Optional


def generate_short_uuid() -> str:
    """Generate a short UUID (7 characters) for use in branch names and directory names."""
    uuid_str = str(uuid.uuid4())
    sha256_hash = hashlib.sha256(uuid_str.encode()).hexdigest()
    return sha256_hash[:7]


def generate_branch_name(
    ticket_id: Optional[str] = None,
    short_name: Optional[str] = None,
) -> str:
    """
    Generate a branch name in the format: u/codebot/[TICKET-ID/]<uuid>/<short-name>
    
    Args:
        ticket_id: Optional ticket ID (e.g., "PROJ-123")
        short_name: Short descriptive name for the task
        
    Returns:
        Branch name string
    """
    uuid_part = generate_short_uuid()
    
    parts = ["u", "codebot"]
    
    if ticket_id:
        parts.append(ticket_id)
    
    parts.append(uuid_part)
    
    if short_name:
        parts.append(short_name)
    
    return "/".join(parts)


def generate_directory_name(ticket_id: Optional[str] = None) -> str:
    """
    Generate a directory name in the format: task_[TICKET-ID_]uuid
    
    Args:
        ticket_id: Optional ticket ID (e.g., "PROJ-123")
        
    Returns:
        Directory name string
    """
    uuid_part = generate_short_uuid()
    
    if ticket_id:
        return f"task_{ticket_id}_{uuid_part}"
    else:
        return f"task_{uuid_part}"
