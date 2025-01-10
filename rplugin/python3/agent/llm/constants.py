SYSTEM_PROMPT = "You are an AI assistant embedded into Neovim text editor."
CLAUDE_SONNET = "claude-3-5-sonnet-latest"
BEDROCK_CLAUDE = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
US_EAST_1 = "us-east-1"
MAX_TOKENS = 4096
TEMPERATURE = 0.7

BASE_SYSTEM_PROMPT = "You are an AI agent embedded into Neovim, a text editor."

FILE_CONTEXT_SYSTEM_PROMPT = """You have access to files from your environment, which provide context for your tasks.

- Each file has a path, line count, content
- A file is active if it is open in the editor
- This information is crucial for understanding the current editing context

<context_files>
{{FILES}}
</context_files>"""

FILE_CONTEXT_PROMPT = """
================================================
File: {{FILE}}
Lines: {{LINES}}
Active: {{ACTIVE}}
================================================
{{CONTENT}}

"""


def create_file_prompt_from_buf(buf):
    content = "\n".join(buf[:]).strip()
    return _create_file_context_prompt(buf.name, content, str(len(buf)), True)


def create_file_prompt_from_file(file_path):
    try:
        lines = open(file_path, "r").readlines()
        return _create_file_context_prompt(file_path, "".join(lines), len(lines))
    except Exception:
        return None


def _create_file_context_prompt(file_path: str, content: str, lines: int, active: bool = False):
    return (
        FILE_CONTEXT_PROMPT.replace("{{FILE}}", file_path)
        .replace("{{LINES}}", str(lines))
        .replace("{{ACTIVE}}", str(active))
        .replace("{{CONTENT}}", content)
        .lstrip()
    )
