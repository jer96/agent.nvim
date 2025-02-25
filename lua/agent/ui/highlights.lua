local M = {}

local function setup_highlights()
  local colors = require("kanagawa.colors").setup()
  -- Message role highlights
  vim.api.nvim_set_hl(0, "MessageUser", { fg = colors.palette.crystalBlue, bold = true })
  vim.api.nvim_set_hl(0, "MessageAssistant", { fg = colors.palette.springGreen, bold = true })
  vim.api.nvim_set_hl(0, "MessageSystem", { fg = colors.palette.oniViolet, bold = true })

  -- Tool highlights
  vim.api.nvim_set_hl(0, "MessageToolCall", { fg = colors.palette.springViolet2 })
  vim.api.nvim_set_hl(0, "MessageToolSuccess", { fg = colors.palette.springGreen })
  vim.api.nvim_set_hl(0, "MessageToolError", { fg = colors.palette.peachRed })

  -- Message content highlights
  vim.api.nvim_set_hl(0, "MessageContent", { link = "Normal" })
end

function M.setup()
  setup_highlights()

  -- Create an autocmd to refresh highlights on colorscheme change
  vim.api.nvim_create_autocmd("ColorScheme", {
    pattern = "*",
    callback = setup_highlights,
  })
end

return M
