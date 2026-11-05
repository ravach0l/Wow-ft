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

-- Forever hat die alte Fertigkeitenliste nicht mehr: Berufe kommen über
-- GetProfessions/GetProfessionInfo (Haupt-, Archäologie-, Angel-, Kochberuf).
function Collect.Skills()
  local out = {}
  if GetProfessions and GetProfessionInfo then
    local labels = { "Berufe", "Berufe", "Nebenberufe", "Nebenberufe", "Nebenberufe" }
    local indices = { GetProfessions() }
    for slot = 1, 5 do
      local index = indices[slot]
      if index then
        local name, _, rank, max = GetProfessionInfo(index)
        if name then
          out[#out + 1] = { name = name, rank = rank, max = max, header = labels[slot] }
        end
      end
    end
    return out
  end
  local header
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

-- Forever: C_Reputation liefert Tabellen statt vieler Rückgabewerte.
function Collect.Reputation()
  local out = {}
  if C_Reputation and C_Reputation.GetNumFactions and C_Reputation.GetFactionDataByIndex then
    for i = 1, C_Reputation.GetNumFactions() do
      local data = C_Reputation.GetFactionDataByIndex(i)
      if data and data.name and (not data.isHeader or data.isHeaderWithRep) then
        out[#out + 1] = {
          id = data.factionID,
          name = data.name,
          standing = data.reaction,
          value = data.currentStanding,
          min = data.currentReactionThreshold,
          max = data.nextReactionThreshold,
        }
      end
    end
    return out
  end
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

local function SpellNameById(spellID)
  if not spellID then
    return nil
  end
  if C_Spell and C_Spell.GetSpellName then
    return C_Spell.GetSpellName(spellID)
  end
  return GetSpellInfo and (GetSpellInfo(spellID))
end

-- Forever: Talente liegen in modernen Talentbäumen (C_ClassTalents + C_Traits).
local function TraitTalents()
  local configID = C_ClassTalents.GetActiveConfigID()
  if not configID then
    return {}
  end
  local config = C_Traits.GetConfigInfo(configID)
  local tabs = {}
  for _, treeID in ipairs(config and config.treeIDs or {}) do
    local points, list = 0, {}
    for _, nodeID in ipairs(C_Traits.GetTreeNodes(treeID) or {}) do
      local node = C_Traits.GetNodeInfo(configID, nodeID)
      if node and (node.currentRank or 0) > 0 then
        local entryID = (node.activeEntry and node.activeEntry.entryID) or (node.entryIDs and node.entryIDs[1])
        local entry = entryID and C_Traits.GetEntryInfo(configID, entryID)
        local def = entry and entry.definitionID and C_Traits.GetDefinitionInfo(entry.definitionID)
        local name = def and (def.overrideName or SpellNameById(def.spellID))
        points = points + node.currentRank
        list[#list + 1] = {
          name = name or ("Talent " .. tostring(nodeID)),
          rank = node.currentRank,
          max = node.maxRanks,
          tier = node.posY,
          col = node.posX,
        }
      end
    end
    local specName
    if C_SpecializationInfo and C_SpecializationInfo.GetSpecialization and C_SpecializationInfo.GetSpecializationInfo then
      local spec = C_SpecializationInfo.GetSpecialization()
      specName = spec and select(2, C_SpecializationInfo.GetSpecializationInfo(spec))
    end
    tabs[#tabs + 1] = { name = specName or ("Talentbaum " .. tostring(treeID)), points = points, talents = list }
  end
  return tabs
end

function Collect.Talents()
  if C_ClassTalents and C_ClassTalents.GetActiveConfigID and C_Traits and C_Traits.GetConfigInfo then
    return TraitTalents()
  end
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

-- Forever: GetItemInfoInstant liegt je nach Client in C_Item oder global.
local function IsTradeGood(itemID)
  local fn = (C_Item and C_Item.GetItemInfoInstant) or GetItemInfoInstant
  local classID = select(6, fn(itemID))
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

-- Diagnose für /ft api: Welche Funktionen gibt es in diesem Client? Das Ergebnis
-- landet in WowFTDB.probe und damit nach /reload in der SavedVariables-Datei.
local PROBE_NAMESPACES = {
  "C_Reputation", "C_SkillLine", "C_TradeSkillUI", "C_SpecializationInfo",
  "C_ClassTalents", "C_Traits", "C_Item", "C_Container", "C_CharacterInfo",
}
local PROBE_FUNCTIONS = {
  "GetNumSkillLines", "GetSkillLineInfo", "GetProfessions", "GetProfessionInfo",
  "GetNumFactions", "GetFactionInfo", "GetFactionInfoByID",
  "GetNumTalentTabs", "GetTalentTabInfo", "GetNumTalents", "GetTalentInfo",
  "GetNumSpecializations", "GetSpecialization", "GetSpecializationInfo",
  "GetItemInfoInstant", "GetItemInfo", "GetContainerNumSlots", "GetContainerItemInfo",
  "BNSendGameData", "RequestTimePlayed", "Screenshot",
}

local function Resolve(path)
  local value = _G
  for part in path:gmatch("[^.]+") do
    if type(value) ~= "table" then
      return nil
    end
    value = value[part]
  end
  return value
end

function Collect.Probe()
  local report = { present = {}, missing = {}, namespaces = {}, samples = {} }
  for _, name in ipairs(PROBE_FUNCTIONS) do
    local fn = Resolve(name)
    if type(fn) == "function" then
      report.present[#report.present + 1] = name
    else
      report.missing[#report.missing + 1] = name
    end
  end
  for _, ns_name in ipairs(PROBE_NAMESPACES) do
    local tbl = Resolve(ns_name)
    if type(tbl) == "table" then
      local keys = {}
      for key, value in pairs(tbl) do
        if type(value) == "function" then
          keys[#keys + 1] = tostring(key)
        end
      end
      table.sort(keys)
      report.namespaces[ns_name] = table.concat(keys, " ")
    else
      report.namespaces[ns_name] = "FEHLT"
    end
  end
  -- Ungefährliche Getter ohne Argumente probeweise aufrufen.
  for _, name in ipairs({ "GetProfessions", "GetNumSpecializations", "GetSpecialization",
    "C_Reputation.GetNumFactions", "C_SpecializationInfo.GetNumSpecializations",
    "C_SpecializationInfo.GetSpecialization", "C_ClassTalents.GetActiveConfigID" }) do
    local fn = Resolve(name)
    if type(fn) == "function" then
      local ok, a, b, c, d = pcall(fn)
      report.samples[name] = ok and (tostring(a) .. "," .. tostring(b) .. "," .. tostring(c) .. "," .. tostring(d))
        or ("Fehler: " .. tostring(a))
    end
  end
  local ok, info = pcall(function()
    local configID = C_ClassTalents.GetActiveConfigID()
    local config = C_Traits.GetConfigInfo(configID)
    local trees, nodes, ranked = {}, 0, 0
    for _, treeID in ipairs(config and config.treeIDs or {}) do
      trees[#trees + 1] = tostring(treeID)
      for _, nodeID in ipairs(C_Traits.GetTreeNodes(treeID) or {}) do
        nodes = nodes + 1
        local node = C_Traits.GetNodeInfo(configID, nodeID)
        if node and (node.currentRank or 0) > 0 then
          ranked = ranked + 1
        end
      end
    end
    return ("config=%s trees=%s nodes=%d mitPunkten=%d"):format(tostring(configID), table.concat(trees, "/"), nodes, ranked)
  end)
  report.samples.talentTrees = ok and info or ("Fehler: " .. tostring(info))
  return report
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
