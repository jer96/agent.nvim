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
      table.insert(lines, string.format("%s %s", status_symbol, relative_path))
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
    table.insert(lines, "")
    table.insert(lines, "Commands:")
    table.insert(lines, "- <CR>: Add selected file")
    table.insert(lines, "- <C-d>: Remove selected file/buffer")
    table.insert(lines, "- <C-f>: Clear all files")
    table.insert(lines, "- <C-b>: Clear all buffers")
    table.insert(lines, "- <C-x>: Clear everything")
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

-- Helper function to refresh picker
local function refresh_picker(prompt_bufnr)
  actions.close(prompt_bufnr)
  vim.schedule(function()
    M.file_picker_with_context()
  end)
end

-- Helper function to map both normal and insert modes
local function map_both_modes(prompt_bufnr, map, key, fn)
  map("i", key, fn)
  map("n", key, fn)
end

-- telescope.lua
M.file_picker_with_context = function()
  builtin.find_files({
    prompt_title = "Configure Agent Context",
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

      -- First check if it's a buffer (whether active or not)
      local is_buffer = false
      local is_active = false
      for _, buf in ipairs(context_data.buffers) do
        if vim.fn.fnamemodify(buf.name, ":p") == full_path then
          is_buffer = true
          is_active = buf.active
          break
        end
      end

      -- Only check additional_files if it's not a buffer
      local is_added = false
      if not is_buffer then
        for _, file in ipairs(context_data.files) do
          if vim.fn.fnamemodify(file, ":p") == full_path then
            is_added = true
            break
          end
        end
      end

      -- Add appropriate status indicator
      if is_buffer then
        return (is_active and "✓" or "☐") .. " " .. relative_path
      elseif is_added then
        return "✓ " .. relative_path
      else
        return "☐ " .. relative_path
      end
    end,
    attach_mappings = function(prompt_bufnr, map)
      -- Add file to context and refresh search
      actions.select_default:replace(function()
        local selection = action_state.get_selected_entry()
        local full_path = vim.fn.fnamemodify(selection.value, ":p")

        -- Check if this is a buffer first
        local context_data = vim.fn.AgentContextGetData()
        local is_buffer = false
        for _, buf in ipairs(context_data.buffers) do
          if vim.fn.fnamemodify(buf.name, ":p") == full_path then
            vim.fn.AgentContextToggleBuffer(buf.number)
            is_buffer = true
            break
          end
        end

        -- Only add to additional files if it's not a buffer
        if not is_buffer then
          vim.fn.AgentContextAddFile(full_path)
        end

        refresh_picker(prompt_bufnr)
      end)

      -- Handle file/buffer removal
      local function remove_selected()
        local selection = action_state.get_selected_entry()
        local full_path = vim.fn.fnamemodify(selection.value, ":p")

        -- Check if this is a buffer first
        for _, buf in ipairs(vim.fn.AgentContextGetData().buffers) do
          if vim.fn.fnamemodify(buf.name, ":p") == full_path then
            vim.fn.AgentContextToggleBuffer(buf.number)
            refresh_picker(prompt_bufnr)
            return
          end
        end

        -- If not a buffer, treat as additional file
        vim.fn.AgentContextRemoveFile(full_path)
        refresh_picker(prompt_bufnr)
      end

      -- Map all the commands
      map_both_modes(prompt_bufnr, map, "<C-d>", remove_selected)
      map_both_modes(prompt_bufnr, map, "<C-f>", function()
        vim.fn.AgentContextClearFiles()
        refresh_picker(prompt_bufnr)
      end)
      map_both_modes(prompt_bufnr, map, "<C-b>", function()
        vim.fn.AgentContextClearBuffers()
        refresh_picker(prompt_bufnr)
      end)
      map_both_modes(prompt_bufnr, map, "<C-x>", function()
        vim.fn.AgentContextClearAll()
        refresh_picker(prompt_bufnr)
      end)
      map_both_modes(prompt_bufnr, map, "q", function()
        actions.close(prompt_bufnr)
      end)

      return true
    end,
  })
end

return M
