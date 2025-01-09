local M = {}
local builtin = require("telescope.builtin")
local actions = require("telescope.actions")
local action_state = require("telescope.actions.state")
local previewers = require("telescope.previewers")

-- Custom previewer for context menu
local context_previewer = previewers.new_buffer_previewer({
  title = "Agent Context",
  define_preview = function(self, _, _)
    -- Get current buffer
    local bufnr = self.state.bufnr
    local win = self.state.winid

    -- Call back to get context data
    local context_data = vim.fn.AgentContextGetData()
    if not context_data then
      return
    end

    -- Format the context data
    local lines = {}
    table.insert(lines, "Active Buffers:")
    table.insert(lines, "---------------")

    -- Add buffer contexts
    for _, buf in ipairs(context_data.buffers) do
      local status_symbol = buf.active and "✓" or "☐"
      local relative_path = vim.fn.fnamemodify(buf.name, ":.")
      table.insert(lines, string.format("%s [%d] %s", status_symbol, buf.number, relative_path))
    end

    -- Add additional files
    if #context_data.files > 0 then
      table.insert(lines, "")
      table.insert(lines, "Additional Files:")
      table.insert(lines, "----------------")
      for _, file in ipairs(context_data.files) do
        local relative_path = vim.fn.fnamemodify(file, ":.")
        table.insert(lines, string.format("✓ %s", relative_path))
      end
    end

    -- Add help text
    table.insert(lines, "Commands:")
    table.insert(lines, "- <CR>: Add selected file")
    table.insert(lines, "- <C-d>: Remove selected file")
    table.insert(lines, "- q: Close")

    -- Set the lines in the preview buffer
    vim.api.nvim_buf_set_lines(bufnr, 0, -1, false, lines)

    -- Set up syntax highlighting
    if not self.state.initialized then
      vim.api.nvim_win_set_option(win, "wrap", true)
      vim.api.nvim_win_set_option(win, "cursorline", true)
      vim.api.nvim_buf_set_option(bufnr, "filetype", "agentmenu")

      -- Add highlight groups
      local ns_id = vim.api.nvim_create_namespace("AgentContext")
      for i, line in ipairs(lines) do
        if line:match("^✓") then
          vim.api.nvim_buf_add_highlight(bufnr, ns_id, "String", i - 1, 0, 1)
        elseif line:match("^☐") then
          vim.api.nvim_buf_add_highlight(bufnr, ns_id, "Comment", i - 1, 0, 1)
        elseif line:match("^%-%-") then
          vim.api.nvim_buf_add_highlight(bufnr, ns_id, "Comment", i - 1, 0, -1)
        elseif line:match("^%u") then
          vim.api.nvim_buf_add_highlight(bufnr, ns_id, "Title", i - 1, 0, -1)
        end
      end

      self.state.initialized = true
    end
  end,
})

-- telescope.lua
M.file_picker_with_context = function()
  builtin.find_files({
    prompt_title = "Agent Context Configuration",
    previewer = context_previewer,
    layout_strategy = "horizontal",
    layout_config = {
      width = 0.9,
      height = 0.8,
      preview_width = 0.5,
    },
    path_display = function(_, path)
      -- Get context data to check file status
      local context_data = vim.fn.AgentContextGetData()
      local full_path = vim.fn.fnamemodify(path, ":p")
      local relative_path = vim.fn.fnamemodify(path, ":.")

      -- Check if file is in additional_files (using full path)
      local is_added = false
      for _, file in ipairs(context_data.files) do
        if vim.fn.fnamemodify(file, ":p") == full_path then
          is_added = true
          break
        end
      end

      -- Check if file is an active buffer (using full path)
      if not is_added then
        for _, buf in ipairs(context_data.buffers) do
          if vim.fn.fnamemodify(buf.name, ":p") == full_path and buf.active then
            is_added = true
            break
          end
        end
      end

      -- Add status indicator to path
      if is_added then
        return "✓ " .. relative_path
      else
        return "  " .. relative_path
      end
    end,
    attach_mappings = function(prompt_bufnr, map)
      -- Add file to context and refresh search
      actions.select_default:replace(function()
        local selection = action_state.get_selected_entry()
        local current_picker = action_state.get_current_picker(prompt_bufnr)
        local prompt = current_picker:_get_prompt()

        -- Use the full path from selection.value instead of the displayed path
        vim.fn.AgentContextAddFile(vim.fn.fnamemodify(selection.value, ":p"))

        -- Close and reopen picker with same search
        actions.close(prompt_bufnr)
        vim.schedule(function()
          M.file_picker_with_context()
          vim.api.nvim_feedkeys(prompt, "n", true)
        end)
      end)

      -- Remove file from context
      map("i", "<C-d>", function()
        local selection = action_state.get_selected_entry()
        local current_picker = action_state.get_current_picker(prompt_bufnr)
        local prompt = current_picker:_get_prompt()

        -- Use the full path from selection.value
        vim.fn.AgentContextRemoveFile(vim.fn.fnamemodify(selection.value, ":p"))

        -- Close and reopen picker with same search
        actions.close(prompt_bufnr)
        vim.schedule(function()
          M.file_picker_with_context()
          vim.api.nvim_feedkeys(prompt, "n", true)
        end)
      end)
      map("n", "<C-d>", function()
        local selection = action_state.get_selected_entry()
        local current_picker = action_state.get_current_picker(prompt_bufnr)
        local prompt = current_picker:_get_prompt()

        -- Use the full path from selection.value
        vim.fn.AgentContextRemoveFile(vim.fn.fnamemodify(selection.value, ":p"))

        -- Close and reopen picker with same search
        actions.close(prompt_bufnr)
        vim.schedule(function()
          M.file_picker_with_context()
          vim.api.nvim_feedkeys(prompt, "n", true)
        end)
      end)

      -- Close picker
      map("i", "q", function()
        actions.close(prompt_bufnr)
      end)
      map("n", "q", function()
        actions.close(prompt_bufnr)
      end)

      return true
    end,
  })
end

return M
