### What is Calude-Code Hooks

Claude Code hooks are user-defined shell commands that execute at various points in Claude Code's lifecycle. They provide deterministic control over Claude Code's behavior, ensuring specific actions always occur rather than relying on the LLM to choose to run them.

**Examples of Use Cases:**
*   **Notifications:** Customize how you receive notifications when Claude Code requires input or permission.
*   **Automatic Formatting:** Automatically run code formatters (e.g., `prettier`, `gofmt`) after file edits.
*   **Logging:** Track and count all executed commands for compliance or debugging.
*   **Feedback:** Provide automated feedback when Claude Code produces code that doesn't follow codebase conventions.
*   **Custom Permissions:** Block modifications to sensitive files or directories.

**Important Note:** Hooks execute shell commands with full user permissions without confirmation. Users are responsible for ensuring their hooks are safe and secure, as Anthropic is not liable for any resulting data loss or system damage.

**2. Types and Functions of Hooks (Hook Events):**
Hooks are triggered by specific events in Claude Code's operation:

*   **`PreToolUse`**:
    *   **Function:** Runs after Claude generates tool parameters but *before* the tool call is processed. This hook can block the tool call and provide feedback to Claude.
    *   **Common Matchers:** `Task`, `Bash`, `Glob`, `Grep`, `Read`, `Edit`, `MultiEdit`, `Write`, `WebFetch`, `WebSearch`.
*   **`PostToolUse`**:
    *   **Function:** Runs immediately *after* a tool successfully completes its execution.
    *   **Common Matchers:** Recognizes the same matchers as `PreToolUse`.
*   **`Notification`**:
    *   **Function:** Runs when Claude Code sends notifications, such as when Claude needs permission to use a tool, or when the prompt input has been idle for at least 60 seconds.
*   **`Stop`**:
    *   **Function:** Runs when the main Claude Code agent has finished responding. It does not run if the stoppage was due to a user interrupt.
*   **`SubagentStop`**:
    *   **Function:** Runs when a Claude Code subagent (a Task tool call) has finished responding.
*   **`PreCompact`**:
    *   **Function:** Runs before Claude Code is about to perform a compact operation (e.g., due to a full context window).
    *   **Matchers:** `manual` (invoked from `/compact`) or `auto` (invoked automatically).

**3. Input Patterns for Various Hooks:**
All hooks receive JSON data via `stdin` containing session information and event-specific data.

*   **Common Fields (for all hooks):**
    *   `session_id`: string
    *   `transcript_path`: string (path to conversation JSON)
    *   `hook_event_name`: string (the name of the event that triggered the hook)
*   **`PreToolUse` Input:** Includes `tool_name` (e.g., "Write") and `tool_input` (a JSON object whose schema depends on the specific tool, e.g., `file_path`, `content` for "Write" tool).
*   **`PostToolUse` Input:** Includes `tool_name`, `tool_input` (same as `PreToolUse`), and `tool_response` (a JSON object whose schema depends on the tool, e.g., `filePath`, `success` for "Write" tool).
*   **`Notification` Input:** Includes `message` (the notification message, e.g., "Task completed successfully").
*   **`Stop` and `SubagentStop` Input:** Includes `stop_hook_active` (boolean, true if Claude Code is already continuing due to a stop hook).
*   **`PreCompact` Input:** Includes `trigger` ("manual" or "auto") and `custom_instructions` (string, empty for "auto" trigger).

**4. Output Patterns (Simple, Advanced) for Various Hooks:**

Developers need to choose **one** of these two kind output patterns to implement.

**Simple: Exit Code**
Hooks communicate their status through shell exit codes:
*   **Exit code 0:** Success. `stdout` is shown to the user in transcript mode (CTRL-R). Claude Code does not see `stdout` if the exit code is 0.
*   **Exit code 2:** Blocking error. `stderr` is fed back to Claude for automatic processing. The behavior varies by hook event:
    *   `PreToolUse`: Blocks the tool call, shows error to Claude.
    *   `PostToolUse`: Shows error to Claude (tool already ran).
    *   `Notification`: N/A, shows `stderr` to user only.
    *   `Stop` / `SubagentStop`: Blocks stoppage, shows error to Claude/subagent.
    *   `PreCompact`: N/A, shows `stderr` to user only.
*   **Other exit codes:** Non-blocking error. `stderr` is shown to the user, and execution continues.

**Advanced: JSON Output**
Hooks can return structured JSON in `stdout` for more sophisticated control.

*   **Common JSON Fields (optional, for all hook types):**
    *   `"continue": true | false`: Whether Claude should continue processing after the hook (default: `true`). If `false`, Claude stops.
    *   `"stopReason": "string"`: Message shown when `continue` is `false` (not shown to Claude).
    *   `"suppressOutput": true | false`: Hide `stdout` from transcript mode (default: `false`).
    *   **Note:** If `"continue" = false`, it takes precedence over any `"decision": "block"` output.

*   **Event-Specific JSON Fields:**
    *   **`PreToolUse` Decision Control:**
        *   `"decision": "approve" | "block" | undefined`:
            *   `"approve"`: Bypasses permission system. `reason` is for user.
            *   `"block"`: Prevents tool execution. `reason` is shown to Claude.
            *   `undefined`: Leads to existing permission flow. `reason` is ignored.
        *   `"reason": "Explanation for decision"`
    *   **`PostToolUse` Decision Control:**
        *   `"decision": "block" | undefined`:
            *   `"block"`: Automatically prompts Claude with `reason`.
            *   `undefined`: Does nothing. `reason` is ignored.
        *   `"reason": "Explanation for decision"`
    *   **`Stop` / `SubagentStop` Decision Control:**
        *   `"decision": "block" | undefined`:
            *   `"block"`: Prevents Claude from stopping. `reason` must be provided for Claude to know how to proceed.
            *   `undefined`: Allows Claude to stop. `reason` is ignored.
        *   `"reason": "Must be provided when Claude is blocked from stopping"`
