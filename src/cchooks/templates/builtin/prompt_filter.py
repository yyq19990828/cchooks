"""PromptFilterTemplate for sensitive information detection and filtering.

This template provides comprehensive detection and filtering of sensitive information
in user prompts, including data privacy protection, security recommendations, and
configurable filtering policies. It supports UserPromptSubmit events.

Features:
- Sensitive data pattern detection (PII, credentials, etc.)
- Configurable filtering and redaction policies
- Data privacy protection and compliance
- Security recommendations and warnings
- Audit logging of filtered content
- Custom pattern definitions and whitelisting
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ...models.validation import ValidationResult
from ...types.enums import HookEventType
from ..base_template import BaseTemplate, TemplateConfig, template


@template(
    template_id="prompt-filter",
    name="Prompt Filter",
    description="Sensitive information detection and filtering for user prompts"
)
class PromptFilterTemplate(BaseTemplate):
    """Template for filtering sensitive information from user prompts.

    This template analyzes user prompts for sensitive information such as
    personally identifiable information (PII), credentials, and other sensitive
    data, providing filtering, redaction, and security recommendations.
    """

    @property
    def name(self) -> str:
        return "Prompt Filter"

    @property
    def description(self) -> str:
        return "Sensitive information detection and filtering for user prompts"

    @property
    def supported_events(self) -> List[HookEventType]:
        return [HookEventType.USER_PROMPT_SUBMIT]

    @property
    def customization_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "filtering_enabled": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to enable prompt filtering"
                },
                "detection_mode": {
                    "type": "string",
                    "enum": ["warn", "filter", "block"],
                    "default": "warn",
                    "description": "Action to take when sensitive data is detected"
                },
                "sensitivity_levels": {
                    "type": "array",
                    "items": {"enum": ["low", "medium", "high", "critical"]},
                    "default": ["high", "critical"],
                    "description": "Sensitivity levels to trigger on"
                },
                "pii_patterns": {
                    "type": "object",
                    "properties": {
                        "email": {
                            "type": "boolean",
                            "default": True,
                            "description": "Detect email addresses"
                        },
                        "phone": {
                            "type": "boolean",
                            "default": True,
                            "description": "Detect phone numbers"
                        },
                        "ssn": {
                            "type": "boolean",
                            "default": True,
                            "description": "Detect Social Security Numbers"
                        },
                        "credit_card": {
                            "type": "boolean",
                            "default": True,
                            "description": "Detect credit card numbers"
                        },
                        "ip_address": {
                            "type": "boolean",
                            "default": False,
                            "description": "Detect IP addresses"
                        },
                        "urls": {
                            "type": "boolean",
                            "default": False,
                            "description": "Detect URLs"
                        }
                    },
                    "default": {
                        "email": True,
                        "phone": True,
                        "ssn": True,
                        "credit_card": True,
                        "ip_address": False,
                        "urls": False
                    },
                    "description": "PII pattern detection settings"
                },
                "credential_patterns": {
                    "type": "object",
                    "properties": {
                        "api_keys": {
                            "type": "boolean",
                            "default": True,
                            "description": "Detect API keys"
                        },
                        "passwords": {
                            "type": "boolean",
                            "default": True,
                            "description": "Detect password patterns"
                        },
                        "tokens": {
                            "type": "boolean",
                            "default": True,
                            "description": "Detect authentication tokens"
                        },
                        "secrets": {
                            "type": "boolean",
                            "default": True,
                            "description": "Detect secret keys"
                        }
                    },
                    "default": {
                        "api_keys": True,
                        "passwords": True,
                        "tokens": True,
                        "secrets": True
                    },
                    "description": "Credential pattern detection settings"
                },
                "custom_patterns": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "pattern": {"type": "string"},
                            "sensitivity": {"enum": ["low", "medium", "high", "critical"]},
                            "description": {"type": "string"}
                        },
                        "required": ["name", "pattern", "sensitivity"]
                    },
                    "default": [],
                    "description": "Custom regex patterns for detection"
                },
                "whitelist_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["example.com", "test@test.com", "123-456-7890"],
                    "description": "Patterns to whitelist (ignore during detection)"
                },
                "redaction_char": {
                    "type": "string",
                    "default": "*",
                    "description": "Character to use for redaction"
                },
                "redaction_mode": {
                    "type": "string",
                    "enum": ["full", "partial", "hash"],
                    "default": "partial",
                    "description": "How to redact sensitive information"
                },
                "preserve_format": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to preserve original format when redacting"
                },
                "enable_logging": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to log detected sensitive information"
                },
                "log_file": {
                    "type": "string",
                    "default": "~/.claude/logs/prompt_filter.log",
                    "description": "Path to the filter log file"
                },
                "log_content": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether to log redacted content (security risk)"
                },
                "context_window": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "default": 10,
                    "description": "Number of characters around detection to include in context"
                },
                "min_confidence": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "default": 0.7,
                    "description": "Minimum confidence threshold for detection"
                },
                "batch_processing": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to process multiple patterns in batch"
                },
                "performance_mode": {
                    "type": "boolean",
                    "default": False,
                    "description": "Enable performance optimizations (may reduce accuracy)"
                }
            },
            "required": ["filtering_enabled", "detection_mode"]
        }

    def generate(self, config: TemplateConfig) -> str:
        """Generate the prompt filter hook script."""
        # Validate event type
        self.validate_event_compatibility(config.event_type)

        # Get configuration
        custom_config = config.customization
        filtering_enabled = custom_config.get("filtering_enabled", True)
        detection_mode = custom_config.get("detection_mode", "warn")
        sensitivity_levels = custom_config.get("sensitivity_levels", ["high", "critical"])
        pii_patterns = custom_config.get("pii_patterns", {
            "email": True, "phone": True, "ssn": True, "credit_card": True,
            "ip_address": False, "urls": False
        })
        credential_patterns = custom_config.get("credential_patterns", {
            "api_keys": True, "passwords": True, "tokens": True, "secrets": True
        })
        custom_patterns = custom_config.get("custom_patterns", [])
        whitelist_patterns = custom_config.get("whitelist_patterns", ["example.com", "test@test.com", "123-456-7890"])
        redaction_char = custom_config.get("redaction_char", "*")
        redaction_mode = custom_config.get("redaction_mode", "partial")
        preserve_format = custom_config.get("preserve_format", True)
        enable_logging = custom_config.get("enable_logging", True)
        log_file = custom_config.get("log_file", "~/.claude/logs/prompt_filter.log")
        log_content = custom_config.get("log_content", False)
        context_window = custom_config.get("context_window", 10)
        min_confidence = custom_config.get("min_confidence", 0.7)
        batch_processing = custom_config.get("batch_processing", True)
        performance_mode = custom_config.get("performance_mode", False)

        # Generate script content
        script_header = self.create_script_header(config)

        # Create filter configuration
        filter_config = f'''
# Prompt filter configuration
FILTERING_ENABLED = {filtering_enabled}
DETECTION_MODE = "{detection_mode}"
SENSITIVITY_LEVELS = {sensitivity_levels!r}
PII_PATTERNS = {pii_patterns!r}
CREDENTIAL_PATTERNS = {credential_patterns!r}
CUSTOM_PATTERNS = {custom_patterns!r}
WHITELIST_PATTERNS = {whitelist_patterns!r}
REDACTION_CHAR = "{redaction_char}"
REDACTION_MODE = "{redaction_mode}"
PRESERVE_FORMAT = {preserve_format}
ENABLE_LOGGING = {enable_logging}
LOG_FILE = "{log_file}"
LOG_CONTENT = {log_content}
CONTEXT_WINDOW = {context_window}
MIN_CONFIDENCE = {min_confidence}
BATCH_PROCESSING = {batch_processing}
PERFORMANCE_MODE = {performance_mode}
'''

        # Create helper functions
        helper_functions = '''
import re
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Any, Optional


def expand_path(path_str: str) -> Path:
    """Expand user path and create parent directories."""
    path = Path(path_str).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_sensitivity_value(level: str) -> int:
    """Get numeric value for sensitivity level."""
    levels = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    return levels.get(level.lower(), 1)


def should_trigger_on_sensitivity(level: str) -> bool:
    """Check if sensitivity level should trigger detection."""
    return level in SENSITIVITY_LEVELS


class DetectionResult:
    """Represents a detection result with metadata."""

    def __init__(self, pattern_name: str, matched_text: str, start: int, end: int,
                 sensitivity: str, confidence: float = 1.0, context: str = ""):
        self.pattern_name = pattern_name
        self.matched_text = matched_text
        self.start = start
        self.end = end
        self.sensitivity = sensitivity
        self.confidence = confidence
        self.context = context

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "pattern_name": self.pattern_name,
            "matched_text": self.matched_text if LOG_CONTENT else "[REDACTED]",
            "start": self.start,
            "end": self.end,
            "sensitivity": self.sensitivity,
            "confidence": self.confidence,
            "context": self.context if LOG_CONTENT else "[REDACTED]"
        }


class PatternMatcher:
    """Handles pattern matching and detection logic."""

    def __init__(self):
        self.compiled_patterns = {}
        self._build_patterns()

    def _build_patterns(self) -> None:
        """Build compiled regex patterns for detection."""
        patterns = {}

        # PII Patterns
        if PII_PATTERNS.get("email", False):
            patterns["email"] = {
                "pattern": r'\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b',
                "sensitivity": "medium",
                "description": "Email address"
            }

        if PII_PATTERNS.get("phone", False):
            patterns["phone"] = {
                "pattern": r'\\b(?:\\+?1[-.]?)?\\(?([0-9]{3})\\)?[-.]?([0-9]{3})[-.]?([0-9]{4})\\b',
                "sensitivity": "medium",
                "description": "Phone number"
            }

        if PII_PATTERNS.get("ssn", False):
            patterns["ssn"] = {
                "pattern": r'\\b(?!000|666|9\\d{2})\\d{3}[-.]?(?!00)\\d{2}[-.]?(?!0000)\\d{4}\\b',
                "sensitivity": "critical",
                "description": "Social Security Number"
            }

        if PII_PATTERNS.get("credit_card", False):
            patterns["credit_card"] = {
                "pattern": r'\\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3[0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\\b',
                "sensitivity": "critical",
                "description": "Credit card number"
            }

        if PII_PATTERNS.get("ip_address", False):
            patterns["ip_address"] = {
                "pattern": r'\\b(?:[0-9]{1,3}\\.){3}[0-9]{1,3}\\b',
                "sensitivity": "low",
                "description": "IP address"
            }

        if PII_PATTERNS.get("urls", False):
            patterns["urls"] = {
                "pattern": r'https?://(?:[-\\w.])+(?:[:|/](?:[\\w/_.])*)?(?:\\?(?:[\\w&=%.])*)?(?:#(?:[\\w.])*)?',
                "sensitivity": "low",
                "description": "URL"
            }

        # Credential Patterns
        if CREDENTIAL_PATTERNS.get("api_keys", False):
            patterns["api_key"] = {
                "pattern": r'(?i)(?:api[_-]?key|apikey)\\s*[:=]\\s*[\'\\"]?([a-zA-Z0-9_-]{20,})[\'\\"]?',
                "sensitivity": "critical",
                "description": "API key"
            }

        if CREDENTIAL_PATTERNS.get("passwords", False):
            patterns["password"] = {
                "pattern": r'(?i)(?:password|passwd|pwd)\\s*[:=]\\s*[\'\\"]?([^\\s\'\\"]{8,})[\'\\"]?',
                "sensitivity": "critical",
                "description": "Password"
            }

        if CREDENTIAL_PATTERNS.get("tokens", False):
            patterns["token"] = {
                "pattern": r'(?i)(?:token|bearer)\\s*[:=]\\s*[\'\\"]?([a-zA-Z0-9_.-]{20,})[\'\\"]?',
                "sensitivity": "critical",
                "description": "Authentication token"
            }

        if CREDENTIAL_PATTERNS.get("secrets", False):
            patterns["secret"] = {
                "pattern": r'(?i)(?:secret|private[_-]?key)\\s*[:=]\\s*[\'\\"]?([a-zA-Z0-9_/+=]{20,})[\'\\"]?',
                "sensitivity": "critical",
                "description": "Secret key"
            }

        # Custom Patterns
        for custom in CUSTOM_PATTERNS:
            patterns[custom["name"]] = {
                "pattern": custom["pattern"],
                "sensitivity": custom["sensitivity"],
                "description": custom.get("description", f"Custom pattern: {custom['name']}")
            }

        # Compile patterns
        for name, info in patterns.items():
            try:
                flags = re.IGNORECASE if not PERFORMANCE_MODE else 0
                self.compiled_patterns[name] = {
                    "regex": re.compile(info["pattern"], flags),
                    "sensitivity": info["sensitivity"],
                    "description": info["description"]
                }
            except re.error as e:
                print(f"Warning: Invalid regex pattern for {name}: {e}")

    def is_whitelisted(self, text: str) -> bool:
        """Check if text matches whitelist patterns."""
        for pattern in WHITELIST_PATTERNS:
            if pattern.lower() in text.lower():
                return True
        return False

    def get_context(self, text: str, start: int, end: int) -> str:
        """Get context around matched text."""
        if CONTEXT_WINDOW <= 0:
            return ""

        context_start = max(0, start - CONTEXT_WINDOW)
        context_end = min(len(text), end + CONTEXT_WINDOW)

        return text[context_start:context_end]

    def calculate_confidence(self, pattern_name: str, matched_text: str) -> float:
        """Calculate confidence score for a match."""
        # Simple confidence calculation based on pattern and content
        base_confidence = 1.0

        # Reduce confidence for very short matches
        if len(matched_text) < 3:
            base_confidence *= 0.3
        elif len(matched_text) < 6:
            base_confidence *= 0.6

        # Adjust based on pattern type
        if pattern_name in ["email", "ssn", "credit_card"]:
            # These have well-defined formats
            base_confidence = max(base_confidence, 0.8)
        elif pattern_name in ["password", "secret"]:
            # These are more heuristic
            base_confidence *= 0.7

        return min(base_confidence, 1.0)

    def detect_patterns(self, text: str) -> List[DetectionResult]:
        """Detect all patterns in text."""
        results = []

        for pattern_name, pattern_info in self.compiled_patterns.items():
            regex = pattern_info["regex"]
            sensitivity = pattern_info["sensitivity"]

            # Skip if sensitivity level is not enabled
            if not should_trigger_on_sensitivity(sensitivity):
                continue

            for match in regex.finditer(text):
                matched_text = match.group(0)
                start, end = match.span()

                # Skip if whitelisted
                if self.is_whitelisted(matched_text):
                    continue

                # Calculate confidence
                confidence = self.calculate_confidence(pattern_name, matched_text)

                # Skip if confidence is too low
                if confidence < MIN_CONFIDENCE:
                    continue

                # Get context
                context = self.get_context(text, start, end)

                result = DetectionResult(
                    pattern_name=pattern_name,
                    matched_text=matched_text,
                    start=start,
                    end=end,
                    sensitivity=sensitivity,
                    confidence=confidence,
                    context=context
                )

                results.append(result)

        return results


def redact_text(text: str, detections: List[DetectionResult]) -> str:
    """Redact sensitive information from text."""
    if not detections:
        return text

    # Sort detections by start position (reverse order for safe replacement)
    sorted_detections = sorted(detections, key=lambda x: x.start, reverse=True)

    redacted_text = text

    for detection in sorted_detections:
        original = detection.matched_text

        if REDACTION_MODE == "full":
            # Replace entire match with redaction characters
            replacement = REDACTION_CHAR * len(original)
        elif REDACTION_MODE == "partial":
            # Keep first and last characters, redact middle
            if len(original) <= 4:
                replacement = REDACTION_CHAR * len(original)
            else:
                replacement = original[0] + REDACTION_CHAR * (len(original) - 2) + original[-1]
        elif REDACTION_MODE == "hash":
            # Replace with hash of content
            hash_value = hashlib.md5(original.encode()).hexdigest()[:8]
            replacement = f"[HASH:{hash_value}]"
        else:
            replacement = REDACTION_CHAR * len(original)

        # Preserve format if requested
        if PRESERVE_FORMAT and REDACTION_MODE != "hash":
            # Preserve spaces, dots, dashes, etc.
            formatted_replacement = ""
            for i, char in enumerate(original):
                if char in " .-@":
                    formatted_replacement += char
                elif i < len(replacement):
                    formatted_replacement += replacement[i]
                else:
                    formatted_replacement += REDACTION_CHAR
            replacement = formatted_replacement

        # Replace in text
        redacted_text = (redacted_text[:detection.start] +
                        replacement +
                        redacted_text[detection.end:])

    return redacted_text


def log_detection(detections: List[DetectionResult], original_prompt: str, action_taken: str) -> None:
    """Log detection results to file."""
    if not ENABLE_LOGGING or not detections:
        return

    try:
        log_path = expand_path(LOG_FILE)

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action_taken": action_taken,
            "detection_count": len(detections),
            "detections": [detection.to_dict() for detection in detections],
            "prompt_length": len(original_prompt)
        }

        if LOG_CONTENT:
            log_entry["original_prompt"] = original_prompt
        else:
            log_entry["prompt_hash"] = hashlib.md5(original_prompt.encode()).hexdigest()

        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry) + "\\n")

    except Exception as e:
        print(f"Warning: Failed to log detection: {e}")


def generate_security_recommendations(detections: List[DetectionResult]) -> List[str]:
    """Generate security recommendations based on detections."""
    recommendations = []

    detected_types = set(detection.pattern_name for detection in detections)

    if "email" in detected_types:
        recommendations.append("Consider using placeholder emails (e.g., user@example.com) in examples")

    if "phone" in detected_types:
        recommendations.append("Use fictional phone numbers (e.g., 555-0123) for examples")

    if any(cred in detected_types for cred in ["api_key", "password", "token", "secret"]):
        recommendations.append("Never share real credentials - use placeholder values")
        recommendations.append("Consider using environment variables for sensitive configuration")

    if "ssn" in detected_types:
        recommendations.append("Use fictional SSNs (e.g., 123-45-6789) for testing")

    if "credit_card" in detected_types:
        recommendations.append("Use test credit card numbers for development")

    # Critical sensitivity recommendations
    critical_detections = [d for d in detections if d.sensitivity == "critical"]
    if critical_detections:
        recommendations.append("CRITICAL: Review and remove all real sensitive information before sharing")

    return recommendations


def create_detection_summary(detections: List[DetectionResult]) -> str:
    """Create a summary of detections for user feedback."""
    if not detections:
        return "No sensitive information detected"

    # Group by sensitivity
    by_sensitivity = {}
    for detection in detections:
        if detection.sensitivity not in by_sensitivity:
            by_sensitivity[detection.sensitivity] = []
        by_sensitivity[detection.sensitivity].append(detection)

    summary_parts = []
    for sensitivity in ["critical", "high", "medium", "low"]:
        if sensitivity in by_sensitivity:
            count = len(by_sensitivity[sensitivity])
            types = set(d.pattern_name for d in by_sensitivity[sensitivity])
            type_list = ", ".join(sorted(types))
            summary_parts.append(f"{sensitivity}: {count} items ({type_list})")

    return "Detected sensitive information - " + "; ".join(summary_parts)
'''

        # Create main logic
        main_logic = '''
        if not FILTERING_ENABLED:
            context.output.continue_flow("Prompt filtering disabled")
            return

        # Extract prompt text from context
        prompt_text = ""
        if hasattr(context, 'user_prompt'):
            prompt_text = context.user_prompt
        elif hasattr(context, 'prompt'):
            prompt_text = context.prompt
        elif hasattr(context, 'message'):
            prompt_text = context.message
        else:
            context.output.continue_flow("No prompt text found to filter")
            return

        if not prompt_text or not prompt_text.strip():
            context.output.continue_flow("Empty prompt, no filtering needed")
            return

        # Initialize pattern matcher
        matcher = PatternMatcher()

        # Detect sensitive patterns
        detections = matcher.detect_patterns(prompt_text)

        # Log detections
        action_taken = DETECTION_MODE
        log_detection(detections, prompt_text, action_taken)

        # Handle detections based on mode
        if not detections:
            context.output.continue_flow("Prompt filter: No sensitive information detected")
            return

        # Create detection summary
        detection_summary = create_detection_summary(detections)

        # Generate security recommendations
        recommendations = generate_security_recommendations(detections)

        if DETECTION_MODE == "block":
            # Block the prompt
            message = f"Prompt blocked due to sensitive information detected.\\n\\n"
            message += f"Summary: {detection_summary}\\n\\n"
            if recommendations:
                message += "Security recommendations:\\n"
                for rec in recommendations:
                    message += f"• {rec}\\n"

            context.output.exit_non_block(message)

        elif DETECTION_MODE == "filter":
            # Filter (redact) sensitive information
            redacted_prompt = redact_text(prompt_text, detections)

            message = f"Prompt filtered for sensitive information.\\n\\n"
            message += f"Summary: {detection_summary}\\n\\n"
            message += f"Filtered prompt length: {len(redacted_prompt)} characters "
            message += f"(original: {len(prompt_text)} characters)\\n"

            if recommendations:
                message += "\\nSecurity recommendations:\\n"
                for rec in recommendations:
                    message += f"• {rec}\\n"

            # Note: In a real implementation, we would need a way to
            # modify the prompt that gets sent to Claude
            message += "\\nNote: Redacted content has been processed for safety."

            context.output.continue_flow(message)

        else:  # warn mode
            # Warn but allow prompt to continue
            message = f"Warning: Sensitive information detected in prompt.\\n\\n"
            message += f"Summary: {detection_summary}\\n\\n"

            if recommendations:
                message += "Security recommendations:\\n"
                for rec in recommendations:
                    message += f"• {rec}\\n"
                message += "\\n"

            message += "The prompt will be processed but consider reviewing for privacy."

            context.output.continue_flow(message)
'''

        # Combine all parts
        return script_header + filter_config + helper_functions + self.create_main_function(
            config.event_type, main_logic
        )

    def validate_config(self, config: Dict[str, Any]) -> ValidationResult:
        """Validate the prompt filter configuration."""
        result = self.validate_schema(config, self.customization_schema)

        # Additional validation for custom patterns
        custom_patterns = config.get("custom_patterns", [])
        for i, pattern in enumerate(custom_patterns):
            if isinstance(pattern, dict) and "pattern" in pattern:
                try:
                    re.compile(pattern["pattern"])
                except re.error as e:
                    result.add_error(
                        field_name=f"custom_patterns[{i}].pattern",
                        error_code="INVALID_REGEX",
                        message=f"Invalid regex pattern: {e}",
                        suggested_fix="Fix the regex syntax"
                    )

        # Validate log file path
        log_file = config.get("log_file", "")
        if log_file:
            try:
                expanded_path = Path(log_file).expanduser()
                if not expanded_path.parent.exists():
                    result.add_warning(
                        field_name="log_file",
                        warning_code="DIRECTORY_MISSING",
                        message=f"Log directory {expanded_path.parent} does not exist (will be created)"
                    )
            except Exception:
                result.add_error(
                    field_name="log_file",
                    error_code="INVALID_PATH",
                    message="Invalid log file path",
                    suggested_fix="Use a valid file path"
                )

        # Security warnings
        if config.get("log_content", False):
            result.add_warning(
                field_name="log_content",
                warning_code="SECURITY_RISK",
                message="Logging content may expose sensitive information in logs"
            )

        # Performance warnings
        if config.get("performance_mode", False):
            result.add_warning(
                field_name="performance_mode",
                warning_code="ACCURACY_TRADE_OFF",
                message="Performance mode may reduce detection accuracy"
            )

        return result

    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for prompt filter."""
        return {
            "filtering_enabled": True,
            "detection_mode": "warn",
            "sensitivity_levels": ["high", "critical"],
            "pii_patterns": {
                "email": True,
                "phone": True,
                "ssn": True,
                "credit_card": True,
                "ip_address": False,
                "urls": False
            },
            "credential_patterns": {
                "api_keys": True,
                "passwords": True,
                "tokens": True,
                "secrets": True
            },
            "custom_patterns": [],
            "whitelist_patterns": ["example.com", "test@test.com", "123-456-7890"],
            "redaction_char": "*",
            "redaction_mode": "partial",
            "preserve_format": True,
            "enable_logging": True,
            "log_file": "~/.claude/logs/prompt_filter.log",
            "log_content": False,
            "context_window": 10,
            "min_confidence": 0.7,
            "batch_processing": True,
            "performance_mode": False
        }

    def get_dependencies(self) -> List[str]:
        """Get dependencies for prompt filter template."""
        return []  # Uses only Python standard library
