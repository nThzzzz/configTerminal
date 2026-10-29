-- Movimentação estilo jogos: w/a/s/d no lugar de k/h/j/l.
-- As funções que essas teclas tinham vão para as teclas que ficaram livres:
--   k = kill  (apagar, antigo d)        kk apaga a linha, kiw apaga a palavra
--   j = jump  (flash, antigo s)
--   l = próxima palavra (antigo w)
--   h = append / text object "around" (antigo a)   vhp, khw, ch"
-- Maiúsculas (W, A, S, D, K...) não mudam.
-- <leader>uW liga/desliga e a escolha fica salva para a próxima vez.
local M = {}

local state_file = vim.fn.stdpath("state") .. "/wasd"

M.ai_mappings = { around = "h", around_next = "hn", around_last = "hl" }
local ai_defaults = { around = "a", around_next = "an", around_last = "al" }

local function flash()
  require("flash").jump()
end

-- { modos, tecla, ação, opções }
local wasd_maps = {
  { { "n", "x" }, "w", "v:count == 0 ? 'gk' : 'k'", { expr = true, desc = "Up" } },
  { { "n", "x" }, "s", "v:count == 0 ? 'gj' : 'j'", { expr = true, desc = "Down" } },
  { "o", "w", "k", { desc = "Up" } },
  { "o", "s", "j", { desc = "Down" } },
  { { "n", "x", "o" }, "a", "h", { desc = "Left" } },
  { { "n", "x", "o" }, "d", "l", { desc = "Right" } },
  { { "n", "x", "o" }, "k", "d", { desc = "Delete (kill)" } },
  { { "n", "x", "o" }, "j", flash, { desc = "Flash (jump)" } },
  { { "n", "x", "o" }, "l", "w", { desc = "Next Word" } },
  { "n", "h", "a", { desc = "Append" } },
}

-- o que o LazyVim define por padrão para essas teclas
local default_maps = {
  { { "n", "x" }, "j", "v:count == 0 ? 'gj' : 'j'", { expr = true, desc = "Down" } },
  { { "n", "x" }, "k", "v:count == 0 ? 'gk' : 'k'", { expr = true, desc = "Up" } },
  { { "n", "x", "o" }, "s", flash, { desc = "Flash" } },
}

local active

function M.enabled()
  if active ~= nil then
    return active
  end
  local f = io.open(state_file, "r")
  if not f then
    return true
  end
  local value = f:read("*l")
  f:close()
  return value ~= "off"
end

local function unmap(maps)
  for _, m in ipairs(maps) do
    for _, mode in ipairs(type(m[1]) == "table" and m[1] or { m[1] }) do
      pcall(vim.keymap.del, mode, m[2])
    end
  end
end

-- Para objetos nativos (aw, ap...) o mini.ai devolve "<prefixo><id>", ou seja
-- "hw", que viraria esquerda + palavra. Troca esse "h" pelo `a` nativo.
local function ai_noremap()
  for _, mode in ipairs({ "x", "o" }) do
    for _, lhs in pairs(M.ai_mappings) do
      local m = vim.fn.maparg(lhs, mode, false, true)
      if m.callback and not m.desc:find("(WASD)", 1, true) then
        vim.keymap.set(mode, lhs, function()
          local res = m.callback():gsub("^<Ignore>", "")
          return (res:gsub("^h", "a"))
        end, { expr = true, desc = m.desc .. " (WASD)" })
      end
    end
  end
end

-- troca o prefixo dos text objects "around" do mini.ai (a <-> h)
local function textobjects(on)
  if not package.loaded["mini.ai"] then
    return
  end
  local ai = require("mini.ai")
  local old, new = on and ai_defaults or M.ai_mappings, on and M.ai_mappings or ai_defaults
  for _, mode in ipairs({ "x", "o" }) do
    for _, lhs in pairs(old) do
      pcall(vim.keymap.del, mode, lhs)
    end
  end
  ai.setup(vim.tbl_deep_extend("force", ai.config, { mappings = new }))
  if on then
    ai_noremap()
  end
end

local function apply(on)
  unmap(on and default_maps or wasd_maps)
  -- na inicialização o mini.ai já vem configurado pelo spec (lua/plugins/wasd.lua)
  if active ~= nil then
    textobjects(on)
  end
  for _, m in ipairs(on and wasd_maps or default_maps) do
    vim.keymap.set(m[1], m[2], m[3], vim.tbl_extend("force", { silent = true }, m[4]))
  end
  active = on
end

function M.set(on)
  apply(on)
  local f = io.open(state_file, "w")
  if f then
    f:write(on and "on" or "off")
    f:close()
  end
end

function M.setup()
  apply(M.enabled())
  LazyVim.on_load("mini.ai", function()
    if active then
      ai_noremap()
    end
  end)
  Snacks.toggle({
    name = "WASD",
    get = M.enabled,
    set = M.set,
  }):map("<leader>uW")
end

return M
