local M = {}

M.config = {
  python_host = vim.fn.stdpath("data") .. "/site/pack/plugins/start/agent.nvim/rplugin/python",
  models = {
    default = "claude-3-5-sonnet-20241022",
    available = {
      "claude-3-5-sonnet-20241022",
      "gpt-4",
    },
  },
  api_keys = {
    openai = vim.env.OPENAI_API_KEY,
    anthropic = vim.env.ANTHROPIC_API_KEY,
  },
}

local utils = require("agent.utils")

function M.setup(opts)
  -- Merge user config with defaults
  M.config = vim.tbl_deep_extend("force", M.config, opts or {})

  -- Set global config for python host
  vim.g.agent_config = M.config

  -- Create commands
  require("agent.commands").setup()

  -- Check python host
  if vim.fn.has("python3") ~= 1 then
    utils.log("Error: Python 3 support required", vim.log.levels.ERROR)
    return
  end

  -- Initialize python host
  local python_host = M.config.python_host
  if not vim.fn.isdirectory(python_host) then
    utils.log("Creating Python host directory", vim.log.levels.INFO)
    vim.fn.mkdir(python_host, "p")
  end

  if M.config.enable_logging then
    utils.log("agent.nvim initialized successfully!")
  end
end

return M
