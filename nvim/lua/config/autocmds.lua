-- Autocmds are automatically loaded on the VeryLazy event
-- Default autocmds that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/autocmds.lua
--
-- Add any additional autocmds here
-- with `vim.api.nvim_create_autocmd`
--
-- Or remove existing autocmds by their group name (which is prefixed with `lazyvim_` for the defaults)
-- e.g. vim.api.nvim_del_augroup_by_name("lazyvim_wrap_spell")

-- Autocmd para templates Java
vim.api.nvim_create_autocmd("BufNewFile", {
  pattern = "*.java",
  callback = function()
    -- 1. Insere o conteúdo do arquivo skeleton.java
    vim.cmd("0r ~/.config/nvim/templates/skeleton.java")

    -- 2. Pega o nome do arquivo que você acabou de criar (sem a extensão .java)
    local filename = vim.fn.expand("%:t:r")

    -- 3. Substitui o texto 'CLASS_NAME' pelo nome real do arquivo
    vim.cmd("silent! %s/CLASS_NAME/" .. filename .. "/g")

    -- 4. Move o cursor para a linha 3 (dentro do main) para você já começar a digitar
    vim.cmd("normal! 4G")
    vim.cmd("startinsert!")
  end,
})
