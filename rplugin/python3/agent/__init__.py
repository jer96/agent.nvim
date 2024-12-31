from typing import List

import pynvim

from .llm import LLMProvider


@pynvim.plugin
class AgentPlugin:
    def __init__(self, nvim):
        self.nvim = nvim
        self.llm_provider = LLMProvider(nvim)

    @pynvim.command("AgentDebug", nargs=0, sync=True)
    def debug_info(self):
        """Print debug information"""
        self.nvim.out_write(f"Plugin loaded at: {__file__}\n")
        self.nvim.out_write(f"Current module: {__name__}\n")

    @pynvim.command("TestCommand", nargs="*", range="")
    def testcommand(self, args, range):
        self.nvim.current.line = "Command with args: {}, range: {}".format(args, range)

    @pynvim.autocmd("BufEnter", pattern="*.py", eval='expand("<afile>")', sync=True)
    def on_bufenter(self, filename):
        self.nvim.out_write("testplugin is in " + filename + "\n")

    @pynvim.command("AgentChat", nargs=1, sync=True)
    def complete_text(self, args: List[str]):
        self.nvim.out_write(f"{args[0]}\n")

    @pynvim.function("AgentTest", sync=True)
    def test(self, args: List[str]) -> str:
        self.nvim.out_write(f"{args[0]}\n")
        if not args:
            return ""
        context = args[0]
        try:
            completion = self.llm_provider.complete(context)
            return completion
        except Exception as e:
            self.nvim.err_write(f"Completion error: {str(e)}\n")
            return ""
