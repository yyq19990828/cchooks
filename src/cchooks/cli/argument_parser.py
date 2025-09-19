"""CLI argument parser for cchooks commands.

This module provides the complete argparse-based CLI framework for all cchooks
commands as specified in contracts/cli_commands.yaml. It creates a unified
parser with subcommands for all hook management operations.

Supported commands:
- cc_addhook: Add new hook configuration
- cc_updatehook: Update existing hook configuration
- cc_removehook: Remove hook configuration
- cc_listhooks: List configured hooks
- cc_validatehooks: Validate hook configurations
- cc_generatehook: Generate Python hook script from templates
- cc_registertemplate: Register custom hook template
- cc_listtemplates: List available hook templates
- cc_unregistertemplate: Unregister custom hook template

Usage:
    from cchooks.cli.argument_parser import parse_args

    # Parse command line arguments
    args = parse_args()

    # Access parsed arguments
    print(f"Command: {args.command}")
    print(f"Event: {args.event}")
"""

import argparse
import sys
from typing import Any, Dict, List, Optional, Union

# Valid hook event types as per Claude Code specification
HOOK_EVENTS = [
    "PreToolUse",
    "PostToolUse",
    "Notification",
    "UserPromptSubmit",
    "Stop",
    "SubagentStop",
    "PreCompact",
    "SessionStart",
    "SessionEnd"
]

# Valid settings levels
SETTINGS_LEVELS = ["project", "user"]
SETTINGS_LEVELS_WITH_ALL = ["project", "user", "all"]

# Valid output formats
OUTPUT_FORMATS_BASIC = ["json", "table", "quiet"]
OUTPUT_FORMATS_WITH_YAML = ["json", "table", "yaml"]

# Valid template types for hook generation
TEMPLATE_TYPES = [
    "security-guard",
    "auto-formatter",
    "auto-linter",
    "git-auto-commit",
    "permission-logger",
    "desktop-notifier",
    "task-manager",
    "prompt-filter",
    "context-loader",
    "cleanup-handler"
]

# Valid template sources
TEMPLATE_SOURCES = ["builtin", "user", "file", "plugin", "all"]

# Valid merge methods for pull request
MERGE_METHODS = ["merge", "squash", "rebase"]


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    """Add common arguments shared across multiple commands."""
    parser.add_argument(
        "--level",
        choices=SETTINGS_LEVELS,
        default="project",
        help="Settings level to target (default: project)"
    )

    parser.add_argument(
        "--format",
        choices=OUTPUT_FORMATS_BASIC,
        default="table",
        help="Output format (default: table)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them"
    )

    parser.add_argument(
        "--backup",
        action="store_true",
        default=True,
        help="Create backup before changes (default: true)"
    )

    parser.add_argument(
        "--no-backup",
        dest="backup",
        action="store_false",
        help="Skip backup creation"
    )


def _add_hook_event_argument(parser: argparse.ArgumentParser, required: bool = True) -> None:
    """Add hook event argument."""
    parser.add_argument(
        "event" if required else "--event",
        choices=HOOK_EVENTS,
        help="Hook event type",
        **({} if required else {"required": False})
    )


def _create_addhook_parser(subparsers) -> argparse.ArgumentParser:
    """Create parser for cc_addhook command."""
    parser = subparsers.add_parser(
        "cc_addhook",
        help="Add a new hook configuration to settings file",
        description="Add a new hook configuration to the specified settings file. "
                   "You must provide either --command for shell commands or --script "
                   "for Python script files."
    )

    # Required arguments
    _add_hook_event_argument(parser, required=True)

    # Required one of: command or script
    command_group = parser.add_mutually_exclusive_group(required=True)
    command_group.add_argument(
        "--command",
        help="Shell command to execute"
    )
    command_group.add_argument(
        "--script",
        help="Path to Python script file"
    )

    # Optional arguments
    parser.add_argument(
        "--matcher",
        help="Tool name pattern (required for PreToolUse/PostToolUse events)"
    )

    parser.add_argument(
        "--timeout",
        type=int,
        help="Execution timeout in seconds (1-3600)"
    )

    parser.add_argument(
        "--auto-chmod",
        action="store_true",
        default=True,
        help="Automatically make script executable when using --script (default: true)"
    )

    parser.add_argument(
        "--no-auto-chmod",
        dest="auto_chmod",
        action="store_false",
        help="Skip making script executable"
    )

    # Common arguments
    _add_common_arguments(parser)

    return parser


def _create_updatehook_parser(subparsers) -> argparse.ArgumentParser:
    """Create parser for cc_updatehook command."""
    parser = subparsers.add_parser(
        "cc_updatehook",
        help="Update existing hook configuration",
        description="Update an existing hook configuration. Use cc_listhooks to find "
                   "the index of the hook you want to update."
    )

    # Required arguments
    _add_hook_event_argument(parser, required=True)
    parser.add_argument(
        "index",
        type=int,
        help="Index of hook to update (from cc_listhooks output)"
    )

    # Optional update fields
    parser.add_argument(
        "--command",
        help="New shell command to execute"
    )

    parser.add_argument(
        "--matcher",
        help="New tool name pattern"
    )

    parser.add_argument(
        "--timeout",
        type=int,
        help="New execution timeout in seconds (1-3600)"
    )

    # Common arguments (subset)
    parser.add_argument(
        "--level",
        choices=SETTINGS_LEVELS,
        default="project",
        help="Settings level to target (default: project)"
    )

    parser.add_argument(
        "--format",
        choices=OUTPUT_FORMATS_BASIC,
        default="table",
        help="Output format (default: table)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them"
    )

    parser.add_argument(
        "--backup",
        action="store_true",
        default=True,
        help="Create backup before changes (default: true)"
    )

    parser.add_argument(
        "--no-backup",
        dest="backup",
        action="store_false",
        help="Skip backup creation"
    )

    return parser


def _create_removehook_parser(subparsers) -> argparse.ArgumentParser:
    """Create parser for cc_removehook command."""
    parser = subparsers.add_parser(
        "cc_removehook",
        help="Remove hook configuration from settings",
        description="Remove an existing hook configuration. Use cc_listhooks to find "
                   "the index of the hook you want to remove."
    )

    # Required arguments
    _add_hook_event_argument(parser, required=True)
    parser.add_argument(
        "index",
        type=int,
        help="Index of hook to remove (from cc_listhooks output)"
    )

    # Common arguments (subset)
    parser.add_argument(
        "--level",
        choices=SETTINGS_LEVELS,
        default="project",
        help="Settings level to target (default: project)"
    )

    parser.add_argument(
        "--format",
        choices=OUTPUT_FORMATS_BASIC,
        default="table",
        help="Output format (default: table)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them"
    )

    parser.add_argument(
        "--backup",
        action="store_true",
        default=True,
        help="Create backup before changes (default: true)"
    )

    parser.add_argument(
        "--no-backup",
        dest="backup",
        action="store_false",
        help="Skip backup creation"
    )

    return parser


def _create_listhooks_parser(subparsers) -> argparse.ArgumentParser:
    """Create parser for cc_listhooks command."""
    parser = subparsers.add_parser(
        "cc_listhooks",
        help="List configured hooks",
        description="List all configured hooks, optionally filtered by event type and settings level."
    )

    # Optional arguments
    _add_hook_event_argument(parser, required=False)

    parser.add_argument(
        "--level",
        choices=SETTINGS_LEVELS_WITH_ALL,
        default="all",
        help="Settings level to query (default: all)"
    )

    parser.add_argument(
        "--format",
        choices=OUTPUT_FORMATS_WITH_YAML,
        default="table",
        help="Output format (default: table)"
    )

    return parser


def _create_validatehooks_parser(subparsers) -> argparse.ArgumentParser:
    """Create parser for cc_validatehooks command."""
    parser = subparsers.add_parser(
        "cc_validatehooks",
        help="Validate hook configurations",
        description="Validate all hook configurations for syntax errors, missing files, "
                   "and compliance with Claude Code specifications."
    )

    # Optional arguments
    parser.add_argument(
        "--level",
        choices=SETTINGS_LEVELS_WITH_ALL,
        default="all",
        help="Settings level to validate (default: all)"
    )

    parser.add_argument(
        "--format",
        choices=["json", "table"],
        default="table",
        help="Output format (default: table)"
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors"
    )

    return parser


def _create_generatehook_parser(subparsers) -> argparse.ArgumentParser:
    """Create parser for cc_generatehook command."""
    parser = subparsers.add_parser(
        "cc_generatehook",
        help="Generate Python hook script from predefined templates",
        description="Generate a Python hook script from a predefined template. "
                   "Optionally add the generated script to settings automatically."
    )

    # Required arguments
    parser.add_argument(
        "type",
        choices=TEMPLATE_TYPES,
        help="Hook template type"
    )

    _add_hook_event_argument(parser, required=True)

    parser.add_argument(
        "output",
        help="Output file path for generated script"
    )

    # Optional arguments
    parser.add_argument(
        "--add-to-settings",
        action="store_true",
        help="Automatically add generated script to settings"
    )

    parser.add_argument(
        "--level",
        choices=SETTINGS_LEVELS,
        default="project",
        help="Settings level when add-to-settings is used (default: project)"
    )

    parser.add_argument(
        "--matcher",
        help="Tool matcher pattern (for PreToolUse/PostToolUse events)"
    )

    parser.add_argument(
        "--customization",
        help="Template-specific customization options (JSON format)"
    )

    parser.add_argument(
        "--format",
        choices=OUTPUT_FORMATS_BASIC,
        default="table",
        help="Output format (default: table)"
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing file"
    )

    return parser


def _create_registertemplate_parser(subparsers) -> argparse.ArgumentParser:
    """Create parser for cc_registertemplate command."""
    parser = subparsers.add_parser(
        "cc_registertemplate",
        help="Register a new custom hook template",
        description="Register a custom hook template from a Python file or class. "
                   "Templates can be registered at project or global (user) level."
    )

    # Required arguments
    parser.add_argument(
        "name",
        help="Unique template name/ID"
    )

    # Required one of: file or class
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--file",
        help="Path to Python file containing template class"
    )
    source_group.add_argument(
        "--class",
        help="Fully qualified class name (module.ClassName)"
    )

    # Optional arguments
    parser.add_argument(
        "--description",
        help="Template description"
    )

    parser.add_argument(
        "--events",
        nargs="+",
        choices=HOOK_EVENTS,
        help="Supported hook events"
    )

    parser.add_argument(
        "--version",
        default="1.0.0",
        help="Template version (default: 1.0.0)"
    )

    parser.add_argument(
        "--global",
        dest="global_registry",
        action="store_true",
        help="Register globally (user-level) vs project-level"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing template"
    )

    parser.add_argument(
        "--format",
        choices=OUTPUT_FORMATS_BASIC,
        default="table",
        help="Output format (default: table)"
    )

    return parser


def _create_listtemplates_parser(subparsers) -> argparse.ArgumentParser:
    """Create parser for cc_listtemplates command."""
    parser = subparsers.add_parser(
        "cc_listtemplates",
        help="List available hook templates",
        description="List all available hook templates, including built-in and custom templates."
    )

    # Optional arguments
    _add_hook_event_argument(parser, required=False)

    parser.add_argument(
        "--source",
        choices=TEMPLATE_SOURCES,
        default="all",
        help="Filter by template source (default: all)"
    )

    parser.add_argument(
        "--format",
        choices=OUTPUT_FORMATS_WITH_YAML,
        default="table",
        help="Output format (default: table)"
    )

    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Show customization options"
    )

    return parser


def _create_unregistertemplate_parser(subparsers) -> argparse.ArgumentParser:
    """Create parser for cc_unregistertemplate command."""
    parser = subparsers.add_parser(
        "cc_unregistertemplate",
        help="Unregister a custom hook template",
        description="Unregister a previously registered custom hook template."
    )

    # Required arguments
    parser.add_argument(
        "name",
        help="Template name/ID to unregister"
    )

    # Optional arguments
    parser.add_argument(
        "--global",
        dest="global_registry",
        action="store_true",
        help="Unregister from global (user-level) registry"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force unregister without confirmation"
    )

    parser.add_argument(
        "--format",
        choices=OUTPUT_FORMATS_BASIC,
        default="table",
        help="Output format (default: table)"
    )

    return parser


def _validate_arguments(args: argparse.Namespace) -> None:
    """Validate parsed arguments and apply business logic rules.

    Args:
        args: Parsed command line arguments

    Raises:
        SystemExit: If validation fails
    """
    # Validate timeout range for commands that support it
    if hasattr(args, 'timeout') and args.timeout is not None:
        if args.timeout < 1 or args.timeout > 3600:
            print("错误: timeout 必须在 1-3600 秒之间", file=sys.stderr)
            sys.exit(1)

    # Validate matcher requirement for PreToolUse/PostToolUse events
    if hasattr(args, 'event') and args.event in ("PreToolUse", "PostToolUse"):
        if hasattr(args, 'matcher') and not args.matcher:
            if args.subcommand == "cc_addhook":
                print("错误: PreToolUse 和 PostToolUse 事件需要 --matcher 参数", file=sys.stderr)
                sys.exit(1)

    # Validate customization JSON format
    if hasattr(args, 'customization') and args.customization:
        try:
            import json
            json.loads(args.customization)
        except json.JSONDecodeError as e:
            print(f"错误: --customization 必须是有效的JSON格式: {e}", file=sys.stderr)
            sys.exit(1)

    # Validate index is non-negative
    if hasattr(args, 'index') and args.index < 0:
        print("错误: index 必须是非负整数", file=sys.stderr)
        sys.exit(1)


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the main argument parser.

    Returns:
        Configured ArgumentParser instance
    """
    # Main parser
    parser = argparse.ArgumentParser(
        prog="cchooks",
        description="Claude Code 钩子管理工具 - 管理和自动化Claude Code钩子配置",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 添加新的钩子
  cchooks cc_addhook PreToolUse --command "echo '工具执行前'" --matcher "Write"

  # 列出所有钩子
  cchooks cc_listhooks --format json

  # 从模板生成钩子脚本
  cchooks cc_generatehook security-guard PreToolUse output.py --add-to-settings

  # 验证钩子配置
  cchooks cc_validatehooks --strict

更多信息请参考: contracts/cli_commands.yaml
        """
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0"
    )

    # Create subparsers for each command
    subparsers = parser.add_subparsers(
        dest="subcommand",
        help="可用命令",
        metavar="COMMAND"
    )

    # Add all command parsers
    _create_addhook_parser(subparsers)
    _create_updatehook_parser(subparsers)
    _create_removehook_parser(subparsers)
    _create_listhooks_parser(subparsers)
    _create_validatehooks_parser(subparsers)
    _create_generatehook_parser(subparsers)
    _create_registertemplate_parser(subparsers)
    _create_listtemplates_parser(subparsers)
    _create_unregistertemplate_parser(subparsers)

    # 添加备份管理命令
    from .commands.backup_manager import create_backup_subparser
    create_backup_subparser(subparsers)

    return parser


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command line arguments with validation.

    Args:
        args: List of arguments to parse. If None, uses sys.argv

    Returns:
        Parsed and validated arguments namespace

    Raises:
        SystemExit: If parsing or validation fails
    """
    parser = create_parser()

    # If no arguments provided, show help
    if not args and len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    # Parse arguments
    parsed_args = parser.parse_args(args)

    # If no command specified, show help
    if not parsed_args.subcommand:
        parser.print_help()
        sys.exit(0)

    # Validate arguments
    _validate_arguments(parsed_args)

    return parsed_args


def main() -> None:
    """Main entry point for testing the argument parser."""
    try:
        args = parse_args()
        print(f"解析的子命令: {args.subcommand}")
        print(f"所有参数: {vars(args)}")
    except KeyboardInterrupt:
        print("\n中断操作", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"未预期的错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
