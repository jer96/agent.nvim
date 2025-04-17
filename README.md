# agent.nvim

An LLM agent for Neovim that integrates AI assistance directly into your editing workflow. agent.nvim provides a chat interface where you can interact with an agent equipped with tools to take action in your development environment.

> NOTE: this plugin is experimental and subject to frequent breaking changes.

## Demo 
https://github.com/user-attachments/assets/8dc00c01-4e4a-4007-a7fe-7dbf7633f755

## Features

- Support for streaming respones using either Anthropic or Bedrock API
- Configurable context where buffers and files can be added as context to the agent.
- Model Context Protocol (MCP) Support for tool usage
- Conversation persistence (currently writes to a file on your local disk)

## Requirements
- Model Provider
    - If using Anthropic, set `ANTHROPIC_API_KEY`
    - If using Bedrock, I recommend using [SSO via the AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html). The default credentials on your machine will be used.
- Dependencies
    - Python >=3.7

## Installation

### Using [lazy.nvim](https://github.com/folke/lazy.nvim)

```lua
{
    {
        "jer96/agent.nvim",
        build = ":UpdateRemotePlugins",
        dependencies = {
            "famiu/bufdelete.nvim",
            "nvim-telescope/telescope.nvim",
        },
        config = function()
            require("agent").setup({
                model_provider = "anthropic",
            })
            -- keymaps
            vim.keymap.set("n", "<leader>aa", ":AgentToggle<CR>", { silent = true })
            vim.keymap.set("n", "<leader>ac", require("agent.ui.context").file_picker_with_context)
            vim.keymap.set("n", "<leader>ah", require("agent.ui.conversations").list_conversations)
            -- autocmd to delete open buffer from context 
            vim.api.nvim_create_autocmd("User", {
                pattern = "BDeletePost*",
                callback = function(event)
                    local buf_num = event.file and event.file:match("BDeletePost%s+(%d+)")
                    buf_num = tonumber(buf_num)
                    if buf_num then
                        vim.fn.AgentHandleBufDelete(buf_num)
                    end
                end,
            })
        end,
    },
}
```

## Usage

### Basic Commands

- `:AgentToggle` - Toggle the chat interface on/off
- `:AgentSend` - Send the current message synchronously waiting for response
- `:AgentSendStream` - Send the current message and stream the response
- `:AgentClose` - Close the chat interface
- `:AgentClean` - Clear the current conversation and close the interface
- `:AgentStartConversation` - Start a new conversation

### Context Management

- `:AgentContextAddFile {file}` - Add a specific file to the context
- `:AgentContextRemoveFile {file}` - Remove a file from the context
- `:AgentContextClearFiles` - Clear all additional files from context
- `:AgentContextClearBuffers` - Clear all active buffers from context
- `:AgentContextClearAll` - Clear all context (files and buffers)
- `:AgentContextToggleBuffer {bufnr}` - Toggle inclusion of a specific buffer in context

### Conversation History

- `:AgentListConversations` - List all saved conversations
- `:AgentLoadConversation {id}` - Load a specific conversation by ID
