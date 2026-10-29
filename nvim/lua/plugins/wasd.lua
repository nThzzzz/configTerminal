-- Ajustes de plugins para o modo WASD (ver lua/config/wasd.lua).
-- O que depende do modo é lido na inicialização; depois de <leader>uW,
-- o explorer e as listas só mudam ao reabrir o Neovim.
local wasd = require("config.wasd")

return {
  -- `s` vira "baixo"; o flash é mapeado por config.wasd (j com WASD, s sem)
  {
    "folke/flash.nvim",
    keys = { { "s", mode = { "n", "x", "o" }, false } },
  },

  -- text objects "around": a -> h
  {
    "nvim-mini/mini.ai",
    opts = function(_, opts)
      if wasd.enabled() then
        opts.mappings = vim.tbl_extend("force", opts.mappings or {}, wasd.ai_mappings)
      end
    end,
  },

  -- listas (pickers) e explorer de arquivos
  {
    "folke/snacks.nvim",
    opts = function(_, opts)
      if not wasd.enabled() then
        return
      end
      opts.picker = vim.tbl_deep_extend("force", opts.picker or {}, {
        win = {
          input = { keys = { ["w"] = "list_up", ["s"] = "list_down" } },
          list = { keys = { ["w"] = "list_up", ["s"] = "list_down" } },
        },
        sources = {
          explorer = {
            win = {
              list = {
                keys = {
                  ["a"] = "explorer_close", -- fecha a pasta (esquerda)
                  ["d"] = "confirm", -- abre (direita)
                  ["h"] = "explorer_add", -- antigo a
                  ["k"] = "explorer_del", -- kill, antigo d
                },
              },
            },
          },
        },
      })
    end,
  },
}
