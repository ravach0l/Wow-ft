-- Minimap-Button statt eigener XP-Leiste: Tooltip mit Level, XP und Sync-Stand.
-- Linksklick: Einstellungen · Rechtsklick: Foto · Ziehen: um die Minimap schieben.
-- Läuft ohne Fremdbibliotheken (kein LibDBIcon).
local _, ns = ...
local Util = ns.Util

local UI = {}
ns.UI = UI

local button
local RADIUS_OFFSET = 5
local DEFAULT_ANGLE = 215 -- Grad, unten links wie bei den meisten Addons
local atan2 = math.atan2 or math.atan

local function PlaceButton()
  local angle = math.rad(ns.db.ui.minimapAngle or DEFAULT_ANGLE)
  local radius = (Minimap:GetWidth() / 2) + RADIUS_OFFSET
  button:ClearAllPoints()
  button:SetPoint("CENTER", Minimap, "CENTER", math.cos(angle) * radius, math.sin(angle) * radius)
end

local function UpdateAngleFromCursor()
  local mx, my = Minimap:GetCenter()
  local cx, cy = GetCursorPosition()
  local scale = Minimap:GetEffectiveScale()
  ns.db.ui.minimapAngle = math.deg(atan2(cy / scale - my, cx / scale - mx)) % 360
  PlaceButton()
end

local function ShowTooltip(self)
  GameTooltip:SetOwner(self, "ANCHOR_LEFT")
  GameTooltip:AddLine("WowFT")

  local xpMax = UnitXPMax("player")
  if xpMax and xpMax > 0 then
    GameTooltip:AddLine(
      ("Level %d · %d%% XP"):format(UnitLevel("player"), math.floor(UnitXP("player") / xpMax * 100)),
      1, 1, 1
    )
  else
    GameTooltip:AddLine(("Level %d"):format(UnitLevel("player")), 1, 1, 1)
  end

  local char = ns.CurrentCharacter()
  local last = char and char.snapshots[#char.snapshots]
  if last then
    GameTooltip:AddLine("Letzter Snapshot: " .. Util.Ago(time() - last.t), 0.8, 0.8, 0.8)
  else
    GameTooltip:AddLine("Noch kein Snapshot", 0.8, 0.8, 0.8)
  end
  GameTooltip:AddLine("Gesendet wird erst nach Logout oder /reload.", 0.6, 0.6, 0.6, true)

  local errors = char and char.apiErrors
  if errors and next(errors) then
    local keys = {}
    for key in pairs(errors) do
      keys[#keys + 1] = key
    end
    table.sort(keys)
    GameTooltip:AddLine("API-Problem bei: " .. table.concat(keys, ", "), 1, 0.4, 0.4, true)
  end

  GameTooltip:AddLine(" ")
  GameTooltip:AddLine("Linksklick: Einstellungen", 0.5, 0.8, 1)
  GameTooltip:AddLine("Rechtsklick: Foto aufnehmen", 0.5, 0.8, 1)
  GameTooltip:AddLine("Ziehen: Button verschieben", 0.5, 0.8, 1)
  GameTooltip:Show()
end

local function Build()
  button = CreateFrame("Button", "WowFTMinimapButton", Minimap)
  button:SetSize(31, 31)
  button:SetFrameStrata("MEDIUM")
  button:SetFrameLevel(8)
  button:SetClampedToScreen(true)
  button:RegisterForClicks("LeftButtonUp", "RightButtonUp")
  button:RegisterForDrag("LeftButton")
  button:SetHighlightTexture("Interface\\Minimap\\UI-Minimap-ZoomButton-Highlight")

  local icon = button:CreateTexture(nil, "BACKGROUND")
  icon:SetSize(20, 20)
  icon:SetPoint("CENTER", 0, 1)
  icon:SetTexture("Interface\\Icons\\INV_Misc_Book_09")
  icon:SetTexCoord(0.08, 0.92, 0.08, 0.92)

  local border = button:CreateTexture(nil, "OVERLAY")
  border:SetSize(53, 53)
  border:SetPoint("TOPLEFT")
  border:SetTexture("Interface\\Minimap\\MiniMap-TrackingBorder")

  button:SetScript("OnClick", function(_, mouseButton)
    if mouseButton == "RightButton" then
      ns.Photo.Open()
    else
      ns.Settings.Toggle()
    end
  end)
  button:SetScript("OnDragStart", function(self)
    GameTooltip:Hide()
    self:SetScript("OnUpdate", UpdateAngleFromCursor)
  end)
  button:SetScript("OnDragStop", function(self)
    self:SetScript("OnUpdate", nil)
  end)
  button:SetScript("OnEnter", ShowTooltip)
  button:SetScript("OnLeave", function()
    GameTooltip:Hide()
  end)
end

-- Der Tooltip liest seine Werte beim Öffnen; hier nur aktualisieren, falls er gerade offen ist.
function UI.Refresh()
  if button and button:IsShown() and GameTooltip:GetOwner() == button then
    ShowTooltip(button)
  end
end

function UI.SetShown(shown)
  ns.db.ui.shown = shown
  if button then
    button:SetShown(shown)
  end
end

function UI.Init()
  Build()
  PlaceButton()
  button:SetShown(ns.db.ui.shown ~= false)
end
