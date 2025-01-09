from typing import List

import pynvim

from .chat import ChatInterface
from .context import AgentContext
from .util.logger import setup_logger


@pynvim.plugin
class AgentPlugin:
    def __init__(self, nvim: pynvim.Nvim):
        self.nvim = nvim
        self.context = AgentContext(nvim)
        self.chat_interface = ChatInterface(nvim, self.context)
        setup_logger()

    @pynvim.command("AgentDebug", nargs=0, sync=True)
    def debug_info(self):
        """Print debug information"""
        self.nvim.out_write(f"Plugin loaded at: {__file__}\n")

    @pynvim.command("AgentTest", nargs="*", range="")
    def testcommand(self, args, range):
        self.nvim.current.line = "Command with args: {}, range: {}".format(args, range)

    @pynvim.command("AgentToggle", sync=True)
    def toggle_chat(self):
        if self.chat_interface.is_active:
            self.chat_interface.close_chat()
        else:
            self.chat_interface.show_chat()

    @pynvim.function("AgentSend")
    def send_message(self, args: List[str]):
        self.chat_interface.send_message()

    @pynvim.function("AgentSendStream")
    def send_message_stream(self, args: List[str]):
        self.nvim.async_call(self.chat_interface.send_message_stream)

    @pynvim.function("AgentClose", sync=True)
    def close_chat(self, args: List[str]):
        self.chat_interface.close_chat()

    @pynvim.function("AgentClean", sync=True)
    def clean_chat(self, args: List[str]):
        self.chat_interface.clean_chat()

    @pynvim.command("AgentContext", sync=True)
    def show_context_picker(self):
        self.nvim.command('lua require("agent.telescope").file_picker_with_context()')

    @pynvim.function("AgentContextGetData", sync=True)
    def get_context_data(self, args: List[str]):
        return self.context.get_context_data()

    @pynvim.function("AgentContextAddFile", sync=True)
    def add_file(self, args: List[str]):
        if args and len(args) > 0:
            self.context.add_file(args[0])

    @pynvim.function("AgentContextRemoveFile", sync=True)
    def remove_file(self, args: List[str]):
        if args and len(args) > 0:
            self.context.remove_file(args[0])
