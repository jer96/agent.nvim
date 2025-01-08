SYSTEM_PROMPT = "You are an AI assistant embedded into Neovim text editor."
CLAUDE_SONNET = "claude-3-5-sonnet-latest"
BEDROCK_CLAUDE = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
US_EAST_1 = "us-east-1"
MAX_TOKENS = 4096
TEMPERATURE = 0.7
IGNORED_BUF_FILE_TYPES = {"alpha", "unkown"}

FORMATTED_SYSTEM_PROMPT = """
You are an AI agent embedded into Neovim, a text editor. You have access to the active buffers in the editor, which provide context for your tasks.

The active buffers information is structured as follows:
- Each buffer has a file, number, line count and content
- This information is crucial for understanding the current editing context

Here are the active buffers:
<active_buffers>
{{ACTIVE_BUFFERS}}
</active_buffers>
"""

BUFFER_CONTEXT_PROMPT = """
================================================
File: {{FILE}}
Number: {{NUMBER}}
Lines: {{LINES}}
================================================
{{CONTENT}}

"""
