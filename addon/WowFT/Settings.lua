-- Einstellungsfenster: Server und Upload-Token für den Uploader, dazu die
-- Schalter für Gold, Handwerksmaterialien und den Minimap-Button.
-- Öffnen: Linksklick auf den Minimap-Button oder /ft config.
--
-- Das Addon hat kein Netzwerk. Server und Token landen in WowFTDB.upload; der
-- Uploader liest sie dort (nach Logout oder /reload) und entfernt den Token,
-- bevor er die Datei hochlädt.
local _, ns = ...
local Util = ns.Util

local Settings = {}
ns.Settings = Settings

local frame, serverBox, tokenBox, statusText, goldCheck, materialCheck, minimapCheck

local function MaskToken(token)
  if not token or token == "" then
    return nil
  end
  return token:sub(1, 4) .. "…" .. token:sub(-4)
end

local function Label(parent, text, x, y, template)
  local fs = parent:CreateFontString(nil, "OVERLAY", template or "GameFontNormal")
  fs:SetPoint("TOPLEFT", x, y)
  fs:SetText(text)
  return fs
end

local function MakeEditBox(parent, y)
  local box = CreateFrame("EditBox", nil, parent, "InputBoxTemplate")
  box:SetSize(320, 22)
  box:SetPoint("TOPLEFT", 26, y)
  box:SetAutoFocus(false)
  box:SetMaxLetters(200)
  box:SetScript("OnEscapePressed", function(self)
    self:ClearFocus()
  end)
  box:SetScript("OnEnterPressed", function(self)
    self:ClearFocus()
  end)
  return box
end

local function MakeCheck(parent, text, y)
  local check = CreateFrame("CheckButton", nil, parent, "UICheckButtonTemplate")
  check:SetSize(24, 24)
  check:SetPoint("TOPLEFT", 20, y)
  local label = parent:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
  label:SetPoint("LEFT", check, "RIGHT", 4, 0)
  label:SetText(text)
  return check
end

local function ShowStatus(text, isError)
  statusText:SetText(isError and ("|cffff6666" .. text .. "|r") or text)
end

local function TokenStatus()
  local masked = MaskToken(ns.db.upload.token)
  if masked then
    ShowStatus("Token gespeichert (" .. masked .. ")", false)
  else
    ShowStatus("Noch kein Token eingetragen.", false)
  end
end

-- Füllt das Fenster mit den aktuellen Werten.
function Settings.Load()
  local upload = ns.db.upload
  serverBox:SetText(upload.server or "")
  tokenBox:SetText(upload.token or "")
  local char = ns.CurrentCharacter()
  local settings = char and char.settings or {}
  goldCheck:SetChecked(settings.trackGold == true)
  materialCheck:SetChecked(settings.trackMaterials ~= false)
  minimapCheck:SetChecked(ns.db.ui.shown ~= false)
  TokenStatus()
end

function Settings.Save()
  local server, token, err = Util.NormalizeUpload(serverBox:GetText(), tokenBox:GetText())
  if err then
    ShowStatus(err, true)
    return false
  end
  -- Leere Werte als nil speichern: Dann fehlt der Schlüssel, und der Uploader
  -- nimmt Server und Token aus seiner eigenen Konfiguration.
  ns.db.upload.server = server ~= "" and server or nil
  ns.db.upload.token = token ~= "" and token or nil

  local char = ns.CurrentCharacter()
  if char then
    char.settings.trackGold = goldCheck:GetChecked() and true or false
    char.settings.trackMaterials = materialCheck:GetChecked() and true or false
    if not char.settings.trackMaterials then
      char.materials = nil
    end
  end
  ns.UI.SetShown(minimapCheck:GetChecked() and true or false)

  TokenStatus()
  ns.Print("Einstellungen gespeichert. Mit /reload schreibt WoW sie auf die Platte; danach übernimmt der Uploader sie.")
  return true
end

local function Build()
  frame = CreateFrame("Frame", "WowFTSettingsFrame", UIParent, BackdropTemplateMixin and "BackdropTemplate" or nil)
  frame:SetSize(380, 340)
  frame:SetPoint("CENTER")
  frame:SetFrameStrata("DIALOG")
  frame:SetClampedToScreen(true)
  frame:SetMovable(true)
  frame:EnableMouse(true)
  frame:RegisterForDrag("LeftButton")
  frame:SetScript("OnDragStart", frame.StartMoving)
  frame:SetScript("OnDragStop", frame.StopMovingOrSizing)
  frame:SetBackdrop({
    bgFile = "Interface\\DialogFrame\\UI-DialogBox-Background",
    edgeFile = "Interface\\DialogFrame\\UI-DialogBox-Border",
    tile = true,
    tileSize = 32,
    edgeSize = 32,
    insets = { left = 8, right = 8, top = 8, bottom = 8 },
  })
  frame:Hide()
  -- Esc schließt das Fenster.
  tinsert(UISpecialFrames, "WowFTSettingsFrame")

  Label(frame, "WowFT – Einstellungen", 20, -18, "GameFontNormalLarge")

  Label(frame, "Server-Adresse", 24, -52)
  serverBox = MakeEditBox(frame, -70)

  Label(frame, "Upload-Token (Webseite → Profil)", 24, -104)
  tokenBox = MakeEditBox(frame, -122)
  tokenBox:SetPassword(true)

  statusText = Label(frame, "", 28, -150, "GameFontHighlightSmall")

  goldCheck = MakeCheck(frame, "Gold an Freunde melden", -174)
  materialCheck = MakeCheck(frame, "Handwerksmaterialien erfassen", -200)
  minimapCheck = MakeCheck(frame, "Minimap-Button anzeigen", -226)

  local hint = Label(
    frame,
    "Gesendet wird erst nach Logout oder /reload. Leere Felder: der Uploader nutzt dann seine eigene Konfiguration.",
    24,
    -262,
    "GameFontDisableSmall"
  )
  hint:SetWidth(330)
  hint:SetJustifyH("LEFT")

  local save = CreateFrame("Button", nil, frame, "UIPanelButtonTemplate")
  save:SetSize(110, 24)
  save:SetPoint("BOTTOMRIGHT", -20, 18)
  save:SetText("Speichern")
  save:SetScript("OnClick", Settings.Save)

  local close = CreateFrame("Button", nil, frame, "UIPanelButtonTemplate")
  close:SetSize(110, 24)
  close:SetPoint("RIGHT", save, "LEFT", -8, 0)
  close:SetText("Schließen")
  close:SetScript("OnClick", function()
    frame:Hide()
  end)

  frame:SetScript("OnShow", Settings.Load)
end

function Settings.Toggle()
  if not frame then
    local ok, err = pcall(Build)
    if not ok then
      frame = nil
      ns.Print("Einstellungsfenster konnte nicht erstellt werden: " .. tostring(err))
      return
    end
  end
  if frame:IsShown() then
    frame:Hide()
  else
    frame:Show()
  end
end
