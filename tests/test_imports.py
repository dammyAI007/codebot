"""Test that all imports work correctly."""

def test_imports():
    """Test that all major components can be imported."""
    import codebot
    import codebot.cli
    import codebot.claude_md_detector
    import codebot.claude_runner
    import codebot.environment
    import codebot.git_ops
    import codebot.github_pr
    import codebot.models
    import codebot.orchestrator
    import codebot.parser
    import codebot.utils
    
    # Verify version
    assert hasattr(codebot, '__version__')
    
    print("All imports successful!")


if __name__ == "__main__":
    test_imports()
