-- Todesursache: Die letzten Treffer gegen den eigenen Charakter (aus dem Kampflog) werden
-- in einem kleinen Ringpuffer gehalten; beim Tod kommt der letzte davon in den deathLog.
local _, ns = ...

local Combat = {}
ns.Combat = Combat

local MAX_HITS = 5
local KILL_WINDOW = 10 -- Sekunden: ältere Treffer gelten nicht als Todesursache
local hits = {}

local SPELL_EVENTS = {
  SPELL_DAMAGE = true,
  SPELL_PERIODIC_DAMAGE = true,
  RANGE_DAMAGE = true,
  DAMAGE_SHIELD = true,
  DAMAGE_SPLIT = true,
}

-- Argumente wie CombatLogGetCurrentEventInfo(): 1 Zeit, 2 Unterereignis, 5 Quelle,
-- 8 Ziel-GUID, ab 12 die Parameter des Unterereignisses.
function Combat.Handle(...)
  local _, sub, _, _, sourceName, _, _, destGUID, _, _, _, p12, p13, p14, p15, p16 = ...
  if destGUID == nil or destGUID ~= Combat.playerGUID then
    return
  end
  local hit
  if sub == "SWING_DAMAGE" then
    hit = { source = sourceName, amount = p12, overkill = p13 }
  elseif SPELL_EVENTS[sub] then
    hit = { source = sourceName, spell = p13, amount = p15, overkill = p16 }
  elseif sub == "ENVIRONMENTAL_DAMAGE" then
    hit = { environment = p12, amount = p13, overkill = p14 }
  else
    return
  end
  hit.at = GetTime()
  ns.Util.Push(hits, hit, MAX_HITS)
end

-- Letzter Treffer kurz vor dem Tod, als Tabelle für den deathLog (oder nil).
function Combat.Killer()
  local last = hits[#hits]
  if not last or GetTime() - last.at > KILL_WINDOW then
    return nil
  end
  local overkill = last.overkill
  if type(overkill) ~= "number" or overkill < 0 then
    overkill = nil
  end
  return {
    source = last.source,
    spell = last.spell,
    environment = last.environment,
    amount = last.amount,
    overkill = overkill,
  }
end

function Combat.Reset()
  wipe(hits)
end
