std = "lua51"
max_line_length = 130
globals = { "WowFTDB", "SLASH_WOWFT1", "SlashCmdList" }
read_globals = {
  "BackdropTemplateMixin", "C_Timer", "CreateFrame", "DEFAULT_CHAT_FRAME", "GameTooltip",
  "GetCurrentRegionName", "GetRealmName", "GetRealZoneText", "GetTime", "GetXPExhaustion",
  "GetZoneText", "NUM_CHAT_WINDOWS", "RequestTimePlayed", "UIParent", "UnitClass",
  "UnitFactionGroup", "UnitGUID", "UnitLevel", "UnitName", "UnitRace", "UnitXP", "UnitXPMax",
  "strlower", "strtrim", "time", "wipe", "_G",
  "BANK_CONTAINER", "C_Container", "GetContainerItemInfo", "GetContainerNumSlots", "GetFactionInfo",
  "GetInstanceInfo", "GetInventoryItemLink", "GetInventoryItemQuality", "GetItemInfo", "GetItemInfoInstant",
  "GetMoney", "GetNumFactions", "GetNumSkillLines", "GetNumTalentTabs", "GetNumTalents", "GetSkillLineInfo",
  "GetTalentInfo", "GetTalentTabInfo", "InCombatLockdown", "NUM_BAG_SLOTS", "NUM_BANKBAGSLOTS", "Screenshot",
  -- Forever (Client 1.60.1): moderne Namensräume statt der alten Classic-Funktionen
  "C_ClassTalents", "C_Item", "C_Reputation", "C_SpecializationInfo", "C_Spell", "C_Traits",
  "GetProfessionInfo", "GetProfessions", "GetSpellInfo", "GetSpellTexture", "GetUnitName",
  -- Minimap-Button und Einstellungsfenster
  "GetCursorPosition", "Minimap", "UISpecialFrames", "tinsert",
}
