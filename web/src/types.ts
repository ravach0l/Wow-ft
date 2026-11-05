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
  character: { id: number; name: string; class: string | null };
  ownerName: string;
}

export interface History {
  character: CharacterState | null;
  snapshots: { ts: number; level: number; xp: number; xpMax: number; playedTotal: number | null; zone: string | null }[];
  events: FeedEvent[];
}

export interface GroupDetail {
  id: number;
  name: string;
  role: "owner" | "member";
  inviteCode?: string;
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
