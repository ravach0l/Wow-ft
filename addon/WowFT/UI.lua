-- Kleines Statusfenster: eigenes Level, XP mit erholtem Anteil, letzter Snapshot.
local _, ns = ...
local Util = ns.Util

local UI = {}
ns.UI = UI

local frame, xpBar, restedBar, levelText, xpText, infoText

local function SavePosition()
  local point, _, relPoint, x, y = frame:GetPoint(1)
  ns.db.ui.point = { point, relPoint, x, y }
end

local function Build()
  frame = CreateFrame("Frame", "WowFTStatusFrame", UIParent, BackdropTemplateMixin and "BackdropTemplate" or nil)
  frame:SetSize(200, 58)
  frame:SetFrameStrata("MEDIUM")
  frame:SetClampedToScreen(true)
  frame:SetMovable(true)
  frame:EnableMouse(true)
  frame:RegisterForDrag("LeftButton")
  frame:SetScript("OnDragStart", frame.StartMoving)
  frame:SetScript("OnDragStop", function(self)
    self:StopMovingOrSizing()
    SavePosition()
  end)
  frame:SetBackdrop({
    bgFile = "Interface\\Tooltips\\UI-Tooltip-Background",
    edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
    edgeSize = 12,
    insets = { left = 3, right = 3, top = 3, bottom = 3 },
  })
  frame:SetBackdropColor(0, 0, 0, 0.75)

  levelText = frame:CreateFontString(nil, "OVERLAY", "GameFontNormal")
  levelText:SetPoint("TOPLEFT", 8, -7)

  xpText = frame:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
  xpText:SetPoint("TOPRIGHT", -8, -8)

  restedBar = CreateFrame("StatusBar", nil, frame)
  restedBar:SetPoint("TOPLEFT", 8, -24)
  restedBar:SetPoint("TOPRIGHT", -8, -24)
  restedBar:SetHeight(8)
  restedBar:SetStatusBarTexture("Interface\\TargetingFrame\\UI-StatusBar")
  restedBar:SetStatusBarColor(0.35, 0.55, 1, 0.45)

  xpBar = CreateFrame("StatusBar", nil, restedBar)
  xpBar:SetAllPoints(restedBar)
  xpBar:SetStatusBarTexture("Interface\\TargetingFrame\\UI-StatusBar")
  xpBar:SetStatusBarColor(0.58, 0.3, 0.9, 1)

  local bg = restedBar:CreateTexture(nil, "BACKGROUND")
  bg:SetAllPoints()
  bg:SetColorTexture(1, 1, 1, 0.08)

  infoText = frame:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
  infoText:SetPoint("BOTTOMLEFT", 8, 7)
  infoText:SetPoint("BOTTOMRIGHT", -8, 7)
  infoText:SetJustifyH("LEFT")

  frame:SetScript("OnEnter", function(self)
    GameTooltip:SetOwner(self, "ANCHOR_BOTTOM")
    GameTooltip:AddLine("WowFT")
    GameTooltip:AddLine("Das Spiel speichert nur bei Logout oder /reload.", 1, 1, 1, true)
    GameTooltip:AddLine("Erst danach kann der Uploader den Stand senden.", 1, 1, 1, true)
    GameTooltip:Show()
  end)
  frame:SetScript("OnLeave", function()
    GameTooltip:Hide()
  end)
end

function UI.Refresh()
  if not frame or not frame:IsShown() then
    return
  end
  local level = UnitLevel("player")
  local xp, xpMax = UnitXP("player"), UnitXPMax("player")
  local rested = GetXPExhaustion() or 0
  local max = xpMax > 0 and xpMax or 1

  levelText:SetText(("Level %d"):format(level))
  xpText:SetText(("%d%%"):format(math.floor(xp / max * 100)))
  xpBar:SetMinMaxValues(0, max)
  xpBar:SetValue(xp)
  restedBar:SetMinMaxValues(0, max)
  restedBar:SetValue(math.min(max, xp + rested))

  local char = ns.CurrentCharacter()
  local last = char and char.snapshots[#char.snapshots]
  if last then
    infoText:SetText("Snapshot " .. Util.Ago(time() - last.t) .. " · /reload = Sync")
  else
    infoText:SetText("Noch kein Snapshot")
  end
end

function UI.SetShown(shown)
  ns.db.ui.shown = shown
  frame:SetShown(shown)
  UI.Refresh()
end

function UI.Init()
  Build()
  local p = ns.db.ui.point
  if p then
    frame:SetPoint(p[1], UIParent, p[2], p[3], p[4])
  else
    frame:SetPoint("TOP", UIParent, "TOP", 0, -120)
  end
  frame:SetShown(ns.db.ui.shown ~= false)
  UI.Refresh()
  C_Timer.NewTicker(30, UI.Refresh)
end
