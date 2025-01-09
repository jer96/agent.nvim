SYSTEM_PROMPT = "You are an AI assistant embedded into Neovim text editor."
CLAUDE_SONNET = "claude-3-5-sonnet-latest"
BEDROCK_CLAUDE = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
US_EAST_1 = "us-east-1"
MAX_TOKENS = 4096
TEMPERATURE = 0.7

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


def create_buf_prompt(buf):
    content = "\n".join(buf[:]).strip()
    return (
        BUFFER_CONTEXT_PROMPT.replace("{{FILE}}", buf.name)
        .replace("{{NUMBER}}", str(buf.number))
        .replace("{{LINES}}", str(len(buf)))
        .replace("{{CONTENT}}", content)
    ).lstrip()


def create_buf_prompt_from_file(file_path):
    try:
        lines = open(file_path, "r").readlines()
        return (
            BUFFER_CONTEXT_PROMPT.replace("{{FILE}}", file_path)
            .replace("{{NUMBER}}", "0")
            .replace("{{LINES}}", str(len(lines)))
            .replace("{{CONTENT}}", "".join(lines))
            .lstrip()
        )
    except Exception:
        return None
