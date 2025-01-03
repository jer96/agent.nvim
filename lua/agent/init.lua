local M = {}

local utils = require("agent.utils")

M.config = {}

function M.setup(opts)
  -- Merge user config with defaults
  M.config = vim.tbl_deep_extend("force", M.config, opts or {})

  -- Set global config for python host
  vim.g.agent_config = M.config

  -- Check python host
  if vim.fn.has("python3") ~= 1 then
    utils.log("Error: Python 3 support required", vim.log.levels.ERROR)
    return
  end
end

return M
