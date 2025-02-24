local M = {}

local function setup_highlights()
  local colors = require("kanagawa.colors").setup()

  -- Tool status highlights
  vim.api.nvim_set_hl(0, "ToolPending", { fg = colors.palette.dragonGray, bold = true })
  vim.api.nvim_set_hl(0, "ToolAccepted", { fg = colors.palette.springGreen, bold = true })
  vim.api.nvim_set_hl(0, "ToolRejected", { fg = colors.palette.autumnRed, bold = true })

  -- Message role highlights
  vim.api.nvim_set_hl(0, "MessageUser", { fg = colors.palette.crystalBlue, bold = true })
  vim.api.nvim_set_hl(0, "MessageAssistant", { fg = colors.palette.springGreen, bold = true })
  vim.api.nvim_set_hl(0, "MessageSystem", { fg = colors.palette.oniViolet, bold = true })

  -- Message content highlights
  vim.api.nvim_set_hl(0, "MessageContent", { link = "Normal" })
  vim.api.nvim_set_hl(0, "MessageToolCall", { fg = colors.palette.surimiOrange })
  vim.api.nvim_set_hl(0, "MessageToolResult", { fg = colors.palette.autumnYellow })
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

