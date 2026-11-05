-- /ft foto: Vollbild mit dem 3D-Modell vor neutralem Hintergrund.
-- Nach einem Screenshot wird der Zeitpunkt gespeichert; der Uploader sucht
-- das passende Bild im Screenshots-Ordner und lädt es hoch.
local _, ns = ...

local Photo = {}
ns.Photo = Photo

local frame, model, controls, hint

local function SetHint(text)
  hint:SetText(text)
end

local function Build()
  frame = CreateFrame("Frame", "WowFTPhotoFrame", UIParent)
  frame:SetAllPoints(UIParent)
  frame:SetFrameStrata("FULLSCREEN_DIALOG")
  frame:EnableMouse(true)
  frame:EnableMouseWheel(true)
  frame:EnableKeyboard(true)
  frame:Hide()

  local bg = frame:CreateTexture(nil, "BACKGROUND")
  bg:SetAllPoints()
  bg:SetColorTexture(0.07, 0.07, 0.09, 1)

  model = CreateFrame("PlayerModel", nil, frame)
  model:SetPoint("CENTER", 0, 20)

  controls = CreateFrame("Frame", nil, frame)
  controls:SetPoint("BOTTOM", 0, 40)
  controls:SetSize(460, 70)

  hint = controls:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
  hint:SetPoint("TOP")

  local shoot = CreateFrame("Button", nil, controls, "UIPanelButtonTemplate")
  shoot:SetSize(150, 26)
  shoot:SetPoint("BOTTOMRIGHT", controls, "BOTTOM", -6, 0)
  shoot:SetText("Foto aufnehmen")
  shoot:SetScript("OnClick", function()
    controls:Hide()
    C_Timer.After(0.1, function()
      if not pcall(Screenshot) then
        controls:Show()
        SetHint("Bitte die Screenshot-Taste drücken (Druck).")
      end
    end)
  end)

  local close = CreateFrame("Button", nil, controls, "UIPanelButtonTemplate")
  close:SetSize(150, 26)
  close:SetPoint("BOTTOMLEFT", controls, "BOTTOM", 6, 0)
  close:SetText("Schließen")
  close:SetScript("OnClick", function()
    frame:Hide()
  end)

  frame:SetScript("OnMouseWheel", function(_, delta)
    model:SetFacing((model:GetFacing() or 0) + delta * 0.25)
  end)
  -- ESC schließt; alle anderen Tasten (auch die Screenshot-Taste) gehen ans Spiel.
  frame:SetScript("OnKeyDown", function(self, key)
    if key == "ESCAPE" then
      self:SetPropagateKeyboardInput(false)
      self:Hide()
    else
      self:SetPropagateKeyboardInput(true)
    end
  end)

  frame:RegisterEvent("SCREENSHOT_SUCCEEDED")
  frame:RegisterEvent("SCREENSHOT_FAILED")
  frame:SetScript("OnEvent", function(_, event)
    if not frame:IsShown() then
      return
    end
    controls:Show()
    if event == "SCREENSHOT_SUCCEEDED" then
      Photo.Record(time())
      SetHint("Gespeichert. Nach /reload lädt der Uploader das Bild hoch.")
      C_Timer.After(2, function()
        frame:Hide()
      end)
    else
      SetHint("Screenshot fehlgeschlagen.")
    end
  end)
end

function Photo.Record(t)
  local char = ns.CurrentCharacter()
  if char then
    char.photoRequests = char.photoRequests or {}
    ns.Util.Push(char.photoRequests, t, ns.MAX_PHOTO_REQUESTS)
  end
end

function Photo.Open()
  if InCombatLockdown() then
    ns.Print("Im Kampf geht das nicht.")
    return
  end
  if not frame then
    Build()
  end
  local h = UIParent:GetHeight()
  model:SetSize(h * 0.6, h * 0.85)
  model:SetUnit("player")
  model:SetFacing(0.35)
  controls:Show()
  SetHint("Mausrad dreht den Charakter. ESC schließt.")
  frame:Show()
end
