"""CLI package for cchooks.

This package contains the command-line interface implementation
including argument parsing, command dispatch, and command implementations.

Key modules:
- argument_parser: Complete argparse-based CLI framework with all 9 commands
- main: Entry point functions for each CLI command (console scripts)
- commands/: Individual command implementations (to be implemented)

Available CLI commands:
- cc_addhook: Add new hook configuration
- cc_updatehook: Update existing hook configuration
- cc_removehook: Remove hook configuration
- cc_listhooks: List configured hooks
- cc_validatehooks: Validate hook configurations
- cc_generatehook: Generate Python hook script from templates
- cc_registertemplate: Register custom hook template
- cc_listtemplates: List available hook templates
- cc_unregistertemplate: Unregister custom hook template

The argument_parser module provides full validation, help text, and
compliance with contracts/cli_commands.yaml specifications.
"""

# Export main functions for easy access
from .argument_parser import create_parser, parse_args

__all__ = [
    "parse_args",
    "create_parser"
]
