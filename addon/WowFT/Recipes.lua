-- Rezepte („Wer kann was?“): Beim Öffnen eines Berufsfensters liest das Addon die bekannten
-- Rezepte samt Reagenzien. Unterstützt die klassische API (TradeSkill/Craft) und die moderne
-- (C_TradeSkillUI). Gespeichert wird je Beruf eine Liste in char.recipes.
local _, ns = ...

local Recipes = {}
ns.Recipes = Recipes

local MAX_RECIPES = 400

local function ItemId(link)
  return link and tonumber(link:match("item:(%d+)"))
end

local function ItemName(id)
  if not id then
    return nil
  end
  if C_Item and C_Item.GetItemNameByID then
    local name = C_Item.GetItemNameByID(id)
    if name then
      return name
    end
  end
  return GetItemInfo and (GetItemInfo(id))
end

-- Klassisches Berufsfenster (Schmiedekunst, Alchimie, …)
function Recipes.ScanTradeSkill()
  if not (GetTradeSkillLine and GetNumTradeSkills) then
    return nil
  end
  local profession = GetTradeSkillLine()
  if not profession or profession == "UNKNOWN" then
    return nil
  end
  local list = {}
  for i = 1, GetNumTradeSkills() do
    local name, kind = GetTradeSkillInfo(i)
    if name and kind ~= "header" and kind ~= "subheader" and #list < MAX_RECIPES then
      local recipe = { name = name, item = ItemId(GetTradeSkillItemLink(i)), reagents = {} }
      for j = 1, GetTradeSkillNumReagents(i) do
        local rname, _, count = GetTradeSkillReagentInfo(i, j)
        recipe.reagents[#recipe.reagents + 1] = {
          id = ItemId(GetTradeSkillReagentItemLink(i, j)),
          name = rname,
          count = count,
        }
      end
      list[#list + 1] = recipe
    end
  end
  return profession, list
end

-- Klassisches „Craft“-Fenster (Verzauberkunst, Wildtierausbildung)
function Recipes.ScanCraft()
  if not (GetCraftDisplaySkillLine and GetNumCrafts) then
    return nil
  end
  local profession = GetCraftDisplaySkillLine()
  if not profession then
    return nil
  end
  local list = {}
  for i = 1, GetNumCrafts() do
    local name, _, kind = GetCraftInfo(i)
    if name and kind ~= "header" and #list < MAX_RECIPES then
      local recipe = { name = name, reagents = {} }
      for j = 1, GetCraftNumReagents(i) do
        local rname, _, count = GetCraftReagentInfo(i, j)
        recipe.reagents[#recipe.reagents + 1] = {
          id = ItemId(GetCraftReagentItemLink(i, j)),
          name = rname,
          count = count,
        }
      end
      list[#list + 1] = recipe
    end
  end
  return profession, list
end

-- Moderne API (C_TradeSkillUI), falls Forever sie nutzt
function Recipes.ScanModern()
  local T = C_TradeSkillUI
  if not (T and T.GetAllRecipeIDs and T.GetRecipeInfo) then
    return nil
  end
  local base = T.GetBaseProfessionInfo and T.GetBaseProfessionInfo()
  local profession = base and base.professionName
  if not profession then
    return nil
  end
  local list = {}
  for _, id in ipairs(T.GetAllRecipeIDs() or {}) do
    local info = T.GetRecipeInfo(id)
    if info and info.learned and #list < MAX_RECIPES then
      local recipe = { name = info.name, spell = id, reagents = {} }
      local schematic = T.GetRecipeSchematic and T.GetRecipeSchematic(id, false)
      if schematic then
        recipe.item = schematic.outputItemID
        for _, slot in ipairs(schematic.reagentSlotSchematics or {}) do
          local first = slot.reagents and slot.reagents[1]
          if first and first.itemID then
            recipe.reagents[#recipe.reagents + 1] = {
              id = first.itemID,
              name = ItemName(first.itemID),
              count = slot.quantityRequired,
            }
          end
        end
      end
      list[#list + 1] = recipe
    end
  end
  return profession, list
end

-- Speichert die Rezepte eines Berufs (ersetzt den früheren Stand dieses Berufs).
function Recipes.Store(char, profession, list)
  if not profession or not list or #list == 0 then
    return
  end
  char.recipes = char.recipes or {}
  for i, entry in ipairs(char.recipes) do
    if entry.profession == profession then
      table.remove(char.recipes, i)
      break
    end
  end
  char.recipes[#char.recipes + 1] = { profession = profession, scanned = time(), list = list }
end

-- kind: "tradeskill", "craft" oder "modern"
function Recipes.Scan(char, kind)
  local scanner = ({
    tradeskill = Recipes.ScanTradeSkill,
    craft = Recipes.ScanCraft,
    modern = Recipes.ScanModern,
  })[kind]
  if not scanner then
    return
  end
  local ok, profession, list = pcall(scanner)
  char.apiErrors = char.apiErrors or {}
  if not ok then
    char.apiErrors.recipes = tostring(profession):sub(1, 200)
    return
  end
  char.apiErrors.recipes = nil
  Recipes.Store(char, profession, list)
end
