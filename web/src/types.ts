export interface Me {
  id: number;
  name: string;
  groups: { id: number; name: string; role: "owner" | "member" }[];
}

export interface CharacterState {
  id: number;
  name: string;
  class: string | null;
  race: string | null;
  faction: string | null;
  region: string | null;
  ownerId: number;
  ownerName: string;
  ts: number;
  lastUpload: number | null;
  level: number;
  xp: number;
  xpMax: number;
  rested: number;
  zone: string | null;
  playedTotal: number | null;
  playedLevel: number | null;
  gold: number | null;
  totalXp: number;
  xpPerHour: number | null;
  etaSeconds: number | null;
  behindLeader: number;
  deaths: number | null;
  photoUrl: string | null;
}

export interface Overview {
  group: { id: number; name: string };
  maxLevel: number;
  lastUpload: number | null;
  characters: CharacterState[];
}

export interface FeedEvent {
  id: number;
  ts: number;
  type: string;
  data: Record<string, unknown> | null;
  text: string;
  character: { id: number; name: string; class: string | null };
  ownerName: string;
}

export interface History {
  character: CharacterState | null;
  snapshots: { ts: number; level: number; xp: number; xpMax: number; playedTotal: number | null; zone: string | null }[];
  events: FeedEvent[];
  state: CharacterDetailState;
  photos: { id: number; url: string; ts: number; level: number | null }[];
}

export interface Skill {
  name: string;
  rank: number;
  max: number | null;
  category: "profession" | "secondary" | "weapon";
}

export interface EquipmentItem {
  slot: number;
  slotName: string;
  id: number | null;
  name: string | null;
  quality: number | null;
}

export interface Reputation {
  id: number | null;
  name: string;
  standing: number;
  standingName: string;
  value: number | null;
  min: number | null;
  max: number | null;
}

export interface TalentTab {
  name: string | null;
  points: number;
  talents: { name: string; rank: number; max: number | null }[];
}

export interface MaterialEntry {
  id: number;
  name: string | null;
  count: number;
}

export interface CharacterDetailState {
  skills: Skill[];
  equipment: EquipmentItem[];
  reputation: Reputation[];
  talents: TalentTab[];
  materials: { bags: MaterialEntry[]; bank: MaterialEntry[] | null; bankScanned: number | null } | null;
  deaths: number | null;
}

export interface RaceSeries {
  id: number;
  name: string;
  class: string | null;
  ownerName: string;
  points: [number, number | null, number][];
}

export interface MaterialItem {
  id: number;
  name: string | null;
  total: number;
  holders: {
    characterId: number;
    name: string;
    class: string | null;
    ownerName: string;
    bags: number;
    bank: number;
    bankScanned: number | null;
  }[];
}

export interface GroupDetail {
  id: number;
  name: string;
  role: "owner" | "member";
  inviteCode?: string;
  discordWebhook?: string | null;
  members: { id: number; name: string; role: string }[];
}

export interface UploadToken {
  id: number;
  name: string;
  prefix: string;
  created: number;
  lastUsed: number | null;
  revoked: number | null;
  token?: string;
}

export interface OwnCharacter {
  id: number;
  name: string;
  class: string | null;
  visible: boolean;
  goldVisible: boolean;
  lastUpload: number | null;
}
