-- Messtest für „fast live“: Lässt sich ein Ereignis während des Spiels nach außen geben,
-- ohne /reload? Idee: WoW schreibt bei eingeschaltetem Chat-Protokoll (/chatlog) laufend
-- nach Logs\WoWChatLog.txt; der Uploader liest die Datei mit. Unklar ist in Forever,
--  1. ob ein Addon sich selbst anflüstern darf (und unter welchem Namen, Forever hat Nachnamen),
--  2. ob auch reine Addon-Ausgaben (AddMessage) im Protokoll landen,
--  3. wie schnell WoW die Datei schreibt.
-- /ft livetest schickt dafür markierte Zeilen auf mehreren Wegen; der Uploader misst mit
-- "wowft-uploader -livetest", welche ankommen und mit welcher Verzögerung.
local _, ns = ...

local Live = {}
ns.Live = Live

-- Mögliche Schreibweisen des eigenen Namens als Flüster-Ziel.
function Live.WhisperTargets()
  local first, second = UnitName("player")
  local out, seen = {}, {}
  local function add(label, name)
    if name and name ~= "" and not seen[name] then
      seen[name] = true
      out[#out + 1] = { label = label, name = name }
    end
  end
  add("vorname", first)
  if second and second ~= "" then
    add("leer", first .. " " .. second)
    add("strich", first .. "-" .. second)
  end
  if GetUnitName then
    local ok, full = pcall(GetUnitName, "player", true)
    if ok then
      add("unitname", full)
    end
  end
  return out
end

function Live.Test()
  local stamp = time()
  local before = LoggingChat and LoggingChat()
  if LoggingChat then
    pcall(LoggingChat, true)
  end
  local logging = LoggingChat and LoggingChat()

  -- Weg 1: reine Addon-Ausgabe im Chatfenster
  DEFAULT_CHAT_FRAME:AddMessage(("WFTLIVE %d addmessage"):format(stamp))

  -- Weg 2: an sich selbst flüstern, unter allen denkbaren Namen
  local results = {}
  for _, target in ipairs(Live.WhisperTargets()) do
    local msg = ("WFTLIVE %d whisper-%s"):format(stamp, target.label)
    local ok, err = pcall(SendChatMessage, msg, "WHISPER", nil, target.name)
    results[#results + 1] = target.label .. "=" .. (ok and "ok" or ("Fehler: " .. tostring(err)))
  end

  ns.Print(("Live-Test %d: Chat-Protokoll %s (vorher %s). Flüstern: %s."):format(
    stamp,
    logging and "an" or "aus/unbekannt",
    before and "an" or "aus",
    table.concat(results, ", ")
  ))
  ns.Print("Jetzt prüfen: Uploader mit -livetest starten oder Logs\\WoWChatLog.txt öffnen.")
  ns.Print("Danach schaltet /chatlog das Protokoll wieder aus.")
  return stamp, results
end
