-- Keymaps are automatically loaded on the VeryLazy event
-- Default keymaps that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/keymaps.lua
-- Add any additional keymaps here

-- Movimentação WASD (w/a/s/d = ↑←↓→). Liga/desliga com <leader>uW
require("config.wasd").setup()
