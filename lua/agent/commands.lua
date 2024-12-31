local M = {}

function M.setup()
  vim.api.nvim_create_user_command("AgentGreet", function()
    require("agent.ui").show_greeting()
  end, {})

  vim.api.nvim_create_user_command("LLMChat", function()
    require("agent.ui").show_chat()
  end, {})
end

return M
