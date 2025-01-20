from typing import List

from mcp import StdioServerParameters


def get_file_system_server_params(allowed_dirs: List[str]):
    args = ["-y", "@modelcontextprotocol/server-filesystem"]
    args.extend(allowed_dirs)
    return StdioServerParameters(command="npx", args=args)
