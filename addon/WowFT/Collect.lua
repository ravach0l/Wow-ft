-- Phase 4: Berufe, Ausrüstung, Ruf, Talente und Handwerksmaterialien.
-- Jeder Sammler läuft geschützt (pcall): Weicht die Forever-API ab, fehlt nur
-- dieser eine Wert, und der Fehler landet in char.apiErrors zur Diagnose.
local _, ns = ...

local Collect = {}
ns.Collect = Collect

local TRADEGOODS_CLASS = 7 -- Enum.ItemClass.Tradegoods

local function ItemIdFromLink(link)
  return link and tonumber(link:match("item:(%d+)"))
end

local function NameFromLink(link)
  return link and link:match("%[(.-)%]")
end

function Collect.Skills()
  local out, header = {}, nil
  for i = 1, GetNumSkillLines() do
    local name, isHeader, _, rank, _, _, max = GetSkillLineInfo(i)
    if isHeader then
      header = name
    elseif name then
      out[#out + 1] = { name = name, rank = rank, max = max, header = header }
    end
  end
  return out
end

function Collect.Equipment()
  local out = {}
  for slot = 1, 19 do
    local link = GetInventoryItemLink("player", slot)
    if link then
      out[#out + 1] = {
        slot = slot,
        id = ItemIdFromLink(link),
        name = NameFromLink(link),
        quality = GetInventoryItemQuality("player", slot),
      }
    end
  end
  return out
end

function Collect.Reputation()
  local out = {}
  for i = 1, GetNumFactions() do
    local name, _, standing, barMin, barMax, value, _, _, isHeader, _, hasRep, _, _, factionID = GetFactionInfo(i)
    if name and (not isHeader or hasRep) then
      out[#out + 1] = {
        id = factionID,
        name = name,
        standing = standing,
        value = value,
        min = barMin,
        max = barMax,
      }
    end
  end
  return out
end

function Collect.Talents()
  local out = {}
  for tab = 1, GetNumTalentTabs() do
    -- Classic liefert je nach Client-Version (name, …) oder (id, name, …).
    local a, b = GetTalentTabInfo(tab)
    local tabName = type(a) == "string" and a or b
    local points, list = 0, {}
    for i = 1, GetNumTalents(tab) do
      local name, _, tier, column, rank, maxRank = GetTalentInfo(tab, i)
      if name and rank and rank > 0 then
        points = points + rank
        list[#list + 1] = { name = name, rank = rank, max = maxRank, tier = tier, col = column }
      end
    end
    out[#out + 1] = { name = tabName, points = points, talents = list }
  end
  return out
end

-- Taschen-API: neue (C_Container) und alte Funktionen.
local function ContainerSlots(bag)
  if C_Container and C_Container.GetContainerNumSlots then
    return C_Container.GetContainerNumSlots(bag) or 0
  end
  return GetContainerNumSlots(bag) or 0
end

local function ContainerItem(bag, slot)
  if C_Container and C_Container.GetContainerItemInfo then
    local info = C_Container.GetContainerItemInfo(bag, slot)
    if info then
      return info.itemID, info.stackCount, info.hyperlink
    end
    return nil
  end
  local _, count, _, _, _, _, link, _, _, itemID = GetContainerItemInfo(bag, slot)
  return itemID or ItemIdFromLink(link), count, link
end

local function IsTradeGood(itemID)
  local classID = select(6, GetItemInfoInstant(itemID))
  return classID == TRADEGOODS_CLASS
end

-- Zählt Handwerksmaterialien in den angegebenen Taschen.
function Collect.Materials(bags)
  local counts, names, order = {}, {}, {}
  for _, bag in ipairs(bags) do
    for slot = 1, ContainerSlots(bag) do
      local id, count, link = ContainerItem(bag, slot)
      if id and IsTradeGood(id) then
        if not counts[id] then
          order[#order + 1] = id
          counts[id] = 0
        end
        counts[id] = counts[id] + (count or 1)
        names[id] = names[id] or NameFromLink(link) or GetItemInfo(id)
      end
    end
  end
  local out = {}
  for _, id in ipairs(order) do
    out[#out + 1] = { id = id, name = names[id], count = counts[id] }
  end
  return out
end

function Collect.BagIds()
  local ids = {}
  for bag = 0, (NUM_BAG_SLOTS or 4) do
    ids[#ids + 1] = bag
  end
  return ids
end

function Collect.BankIds()
  local ids = { BANK_CONTAINER or -1 }
  local first = (NUM_BAG_SLOTS or 4) + 1
  for bag = first, first + (NUM_BANKBAGSLOTS or 6) - 1 do
    ids[#ids + 1] = bag
  end
  return ids
end

-- Führt fn geschützt aus und merkt sich Fehler pro Sammler.
function Collect.Safe(char, key, fn, ...)
  local ok, result = pcall(fn, ...)
  char.apiErrors = char.apiErrors or {}
  if ok then
    char.apiErrors[key] = nil
    return result
  end
  char.apiErrors[key] = tostring(result):sub(1, 200)
  return nil
end

-- Alles außer Bank (die ist nur bei geöffnetem Bankfenster lesbar).
function Collect.All(char)
  local settings = char.settings
  char.skills = Collect.Safe(char, "skills", Collect.Skills) or char.skills
  char.equipment = Collect.Safe(char, "equipment", Collect.Equipment) or char.equipment
  char.reputation = Collect.Safe(char, "reputation", Collect.Reputation) or char.reputation
  char.talents = Collect.Safe(char, "talents", Collect.Talents) or char.talents
  if settings.trackMaterials == false then
    char.materials = nil
  else
    char.materials = char.materials or {}
    char.materials.bags = Collect.Safe(char, "bags", Collect.Materials, Collect.BagIds()) or char.materials.bags
  end
end

function Collect.Bank(char)
  if char.settings.trackMaterials == false then
    return
  end
  char.materials = char.materials or {}
  local bank = Collect.Safe(char, "bank", Collect.Materials, Collect.BankIds())
  if bank then
    char.materials.bank = bank
    char.materials.bankScanned = time()
  end
end
