-- lua/agent/ui.lua
local api = vim.api
local M = {}

function M.show_greeting()
  -- Display greeting in a floating window
  local lines = vim.split("hello", "\n")
  local width = 0
  for _, line in ipairs(lines) do
    width = math.max(width, #line)
  end

  local height = #lines
  local buf = vim.api.nvim_create_buf(false, true)

  -- Set buffer lines
  vim.api.nvim_buf_set_lines(buf, 0, -1, false, lines)

  -- Calculate window position
  local win_opts = {
    relative = "editor",
    width = width + 4,
    height = height,
    row = math.floor((vim.o.lines - height) / 2),
    col = math.floor((vim.o.columns - (width + 4)) / 2),
    style = "minimal",
    border = "rounded",
  }

  -- Create and show the floating window
  local win = vim.api.nvim_open_win(buf, true, win_opts)

  -- Auto-close window after 2 seconds
  vim.defer_fn(function()
    if vim.api.nvim_win_is_valid(win) then
      vim.api.nvim_win_close(win, true)
    end
  end, 2000)
end

-- Store chat window and buffer IDs
M.chat_win = nil
M.chat_buf = nil
M.input_buf = nil
M.input_win = nil
M.messages = {}

function M.create_chat_window()
  -- Create main chat buffer
  M.chat_buf = api.nvim_create_buf(false, true)
  api.nvim_buf_set_option(M.chat_buf, "buftype", "nofile")
  api.nvim_buf_set_option(M.chat_buf, "modifiable", false)
  api.nvim_buf_set_name(M.chat_buf, "Agent Chat")

  -- Calculate window dimensions
  local width = math.floor(vim.o.columns * 0.8)
  local height = math.floor(vim.o.lines * 0.8)
  local row = math.floor((vim.o.lines - height) / 2)
  local col = math.floor((vim.o.columns - width) / 2)

  -- Create main chat window
  local win_opts = {
    relative = "editor",
    width = width,
    height = height - 3, -- Leave space for input
    row = row,
    col = col,
    style = "minimal",
    border = "rounded",
    title = " Agent Chat ",
    title_pos = "center",
  }
  M.chat_win = api.nvim_open_win(M.chat_buf, true, win_opts)

  -- Create input buffer
  M.input_buf = api.nvim_create_buf(false, true)
  api.nvim_buf_set_option(M.input_buf, "buftype", "nofile")
  api.nvim_buf_set_option(M.input_buf, "modifiable", true)

  -- Create input window
  local input_opts = {
    relative = "editor",
    width = width,
    height = 3,
    row = row + height - 3,
    col = col,
    style = "minimal",
    border = "rounded",
    title = " Message ",
    title_pos = "center",
  }
  M.input_win = api.nvim_open_win(M.input_buf, false, input_opts)

  -- Set up keymaps for input buffer
  local opts = { noremap = true, silent = true }
  api.nvim_buf_set_keymap(M.input_buf, "n", "<CR>", ':lua require("agent.ui").send_message()<CR>', opts)
  api.nvim_buf_set_keymap(M.input_buf, "i", "<C-CR>", '<Esc>:lua require("agent.ui").send_message()<CR>', opts)
  api.nvim_buf_set_keymap(M.input_buf, "n", "q", ':lua require("agent.ui").close_chat()<CR>', opts)

  -- Set up autocmd for window close
  api.nvim_create_autocmd("WinClosed", {
    pattern = tostring(M.chat_win),
    callback = function()
      M.close_chat()
    end,
  })

  -- Focus input window
  api.nvim_set_current_win(M.input_win)
  api.nvim_command("startinsert")
end

function M.add_message(role, content)
  table.insert(M.messages, { role = role, content = content })
  M.update_chat_display()
end

function M.update_chat_display()
  if not M.chat_buf or not api.nvim_buf_is_valid(M.chat_buf) then
    return
  end

  local display_lines = {}
  for _, msg in ipairs(M.messages) do
    local prefix = msg.role == "user" and "You: " or "Agent: "
    local wrapped_content = vim.split(msg.content, "\n")
    table.insert(display_lines, prefix .. wrapped_content[1])
    for i = 2, #wrapped_content do
      table.insert(display_lines, string.rep(" ", #prefix) .. wrapped_content[i])
    end
    table.insert(display_lines, "")
  end

  api.nvim_buf_set_option(M.chat_buf, "modifiable", true)
  api.nvim_buf_set_lines(M.chat_buf, 0, -1, false, display_lines)
  api.nvim_buf_set_option(M.chat_buf, "modifiable", false)

  -- Scroll to bottom
  api.nvim_win_set_cursor(M.chat_win, { #display_lines, 0 })
end

function M.send_message()
  if not M.input_buf or not api.nvim_buf_is_valid(M.input_buf) then
    return
  end

  local lines = api.nvim_buf_get_lines(M.input_buf, 0, -1, false)
  local message = table.concat(lines, "\n")

  if message:gsub("%s", "") ~= "" then
    -- Clear input buffer
    api.nvim_buf_set_lines(M.input_buf, 0, -1, false, { "" })

    -- Add user message to chat
    M.add_message("user", message)

    -- Get response from LLM
    local response = vim.fn.AgentTest(message)
    if response ~= "" then
      M.add_message("assistant", response)
    end
  end

  -- Reset cursor and keep insert mode
  api.nvim_win_set_cursor(M.input_win, { 1, 0 })
  api.nvim_command("startinsert")
end

function M.close_chat()
  if M.input_win and api.nvim_win_is_valid(M.input_win) then
    api.nvim_win_close(M.input_win, true)
  end
  if M.chat_win and api.nvim_win_is_valid(M.chat_win) then
    api.nvim_win_close(M.chat_win, true)
  end
  M.chat_win = nil
  M.chat_buf = nil
  M.input_win = nil
  M.input_buf = nil
end

function M.show_chat()
  if M.chat_win and api.nvim_win_is_valid(M.chat_win) then
    api.nvim_set_current_win(M.chat_win)
    return
  end
  M.create_chat_window()
end

return M
