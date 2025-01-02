-- lua/agent/ui.lua
local api = vim.api
local M = {}
local state = {
  messages = {},
}

-- Store chat window and buffer IDs
M.chat_win = nil
M.chat_buf = nil
M.input_buf = nil
M.input_win = nil

local show_chat_windows = function()
  -- Create input window as horizontal split
  vim.cmd("split")
  vim.cmd("resize 5")
  M.input_win = api.nvim_get_current_win()
  api.nvim_win_set_buf(M.input_win, M.input_buf)

  -- Set window options
  local win_config = {
    number = false,
    relativenumber = false,
    wrap = true,
    signcolumn = "no",
  }

  for _, win in ipairs({ M.chat_win, M.input_win }) do
    for option, value in pairs(win_config) do
      api.nvim_win_set_option(win, option, value)
    end
  end

  -- Set up autocmd for buffer wipeout
  api.nvim_create_autocmd("BufWipeout", {
    buffer = M.chat_buf,
    callback = function()
      M.close_chat()
    end,
  })

  -- Focus input window
  api.nvim_set_current_win(M.input_win)
  api.nvim_command("startinsert")
end

function M.show_chat()
  -- If windows exist and are valid, focus them
  if M.chat_win and api.nvim_win_is_valid(M.chat_win) then
    api.nvim_set_current_win(M.chat_win)
    return
  end

  -- If buffers exist but windows don't, just create new windows
  if M.chat_buf and api.nvim_buf_is_valid(M.chat_buf) and M.input_buf and api.nvim_buf_is_valid(M.input_buf) then
    show_chat_windows()
    return
  end

  -- If nothing exists, create everything new
  M.create_chat_window()
end

function M.create_chat_window()
  -- Create main chat buffer
  M.chat_buf = api.nvim_create_buf(false, true)
  api.nvim_buf_set_option(M.chat_buf, "buftype", "nofile")
  api.nvim_buf_set_option(M.chat_buf, "modifiable", false)
  pcall(api.nvim_buf_set_name, M.chat_buf, "Agent Chat")

  -- Create the vertical split for chat
  vim.cmd("vsplit")
  vim.cmd("vertical resize 50")
  M.chat_win = api.nvim_get_current_win()
  api.nvim_win_set_buf(M.chat_win, M.chat_buf)

  -- Create input buffer
  M.input_buf = api.nvim_create_buf(false, true)
  api.nvim_buf_set_option(M.input_buf, "buftype", "nofile")
  api.nvim_buf_set_option(M.input_buf, "modifiable", true)

  show_chat_windows()

  -- Set up keymaps for input buffer
  local opts = { noremap = true, silent = true }
  api.nvim_buf_set_keymap(M.input_buf, "n", "<CR>", ':lua require("agent.ui").send_message()<CR>', opts)
  api.nvim_buf_set_keymap(M.input_buf, "i", "<C-s>", '<Esc>:lua require("agent.ui").send_message()<CR>', opts)
  api.nvim_buf_set_keymap(M.input_buf, "n", "q", ':lua require("agent.ui").close_chat()<CR>', opts)
  api.nvim_buf_set_keymap(M.chat_buf, "n", "q", ':lua require("agent.ui").close_chat()<CR>', opts)
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

local update_chat_display = function()
  if not M.chat_buf or not api.nvim_buf_is_valid(M.chat_buf) then
    return
  end

  local display_lines = {}
  for _, msg in ipairs(state.messages) do
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

local add_message = function(role, content)
  vim.g.agent_state = state
  table.insert(state.messages, { role = role, content = content })
  update_chat_display()

  print("Current Messages:")
  for i, msg in ipairs(state.messages) do
    print(string.format("[%d] role: %s, content: %s", i, msg.role, msg.content))
  end
  print("-------------------")
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
    add_message("user", message)

    -- Get response from LLM
    local response = vim.fn.AgentTest(message)
    if response ~= "" then
      add_message("assistant", response)
    end
  end

  -- Reset cursor and keep insert mode
  api.nvim_win_set_cursor(M.input_win, { 1, 0 })
  api.nvim_command("startinsert")
end

return M
