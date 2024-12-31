vim.api.nvim_create_user_command("AgentStart", function()
  require("agent").setup({
    greeting = "Hello from agent.nvim!",
    enable_logging = true, -- turn on logging
    api_keys = {
      openai = vim.env.OPENAI_API_KEY, -- will use environment variable if set
      anthropic = vim.env.ANTHROPIC_API_KEY,
    },
    models = {
      default = "gpt-4",
      available = {
        "gpt-4",
        "gpt-3.5-turbo",
        "anthropic/claude-3-opus",
        "anthropic/claude-3-sonnet",
      },
    },
  })
end, {})
