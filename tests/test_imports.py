"""Test that all imports work correctly."""

def test_imports():
    """Test that all major components can be imported."""
    import codebot
    import codebot.cli
    import codebot.cli_runner.runner
    import codebot.claude.md_detector
    import codebot.claude.runner
    import codebot.core.environment
    import codebot.core.git_ops
    import codebot.core.github_pr
    import codebot.core.models
    import codebot.core.orchestrator
    import codebot.core.parser
    import codebot.core.utils
    import codebot.server.app
    import codebot.server.review_processor
    import codebot.server.review_runner
    
    # Verify version
    assert hasattr(codebot, '__version__')
    
    print("All imports successful!")


if __name__ == "__main__":
    test_imports()
