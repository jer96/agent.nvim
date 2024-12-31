local M = {}

function M.log(message, level)
  level = level or vim.log.levels.INFO
  vim.notify(message, level)
end

return M
