-- conversations.lua
local M = {}

M.list_conversations = function()
  local conversations = vim.fn.AgentListConversations()

  -- Create quickfix items
  local qf_items = {}
  for i, conv in ipairs(conversations) do
    table.insert(qf_items, {
      text = string.format("messages: %d", conv.message_count),
      user_data = conv.id, -- Store the conversation ID for later use
      filename = "conversation id ", -- Use 'conversation id' as filename
      lnum = i, -- Use index as line number
    })
  end

  -- Set the quickfix list
  vim.fn.setqflist(qf_items)

  -- Open the quickfix window
  vim.cmd("copen")

  -- Add custom mapping for loading conversation
  local bufnr = vim.fn.bufnr("%")
  vim.keymap.set("n", "<CR>", function()
    local item = vim.fn.getqflist()[vim.fn.line(".")]
    if item and item.user_data then
      vim.cmd("cclose")
      vim.cmd("AgentLoadConversation " .. item.user_data)
    end
  end, { buffer = bufnr, silent = true })

  -- Add quit mapping
  vim.keymap.set("n", "q", ":cclose<CR>", { buffer = bufnr, silent = true })
end

return M
