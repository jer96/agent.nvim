# agent.nvim 

LLM agent scaffold for neovim.

## Installation

Using [lazy.nvim](https://github.com/folke/lazy.nvim):
```lua
{
    "jer96/agent.nvim",
    config = function()
        require("agent").setup({})
    end
}
```

Using [packer.nvim](https://github.com/wbthomason/packer.nvim):
```lua
use {
    "jer96/agent.nvim",
    config = function()
        require("agent").setup()
    end
}
```

## Configuration

```lua
require("agent").setup({
    greeting = "Hello from agent.nvim!",
})
```

## Commands

- `:AgentGreet` - Display a greeting message

