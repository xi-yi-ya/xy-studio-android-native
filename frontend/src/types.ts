export type Page =
  | 'projects'
  | 'characters'
  | 'scenes'
  | 'shots'
  | 'images'
  | 'videos'
  | 'tasks'
  | 'settings';
export type MediaKey = string;
export type Status =
  | 'new'
  | 'queued'
  | 'submitting'
  | 'running'
  | 'downloading'
  | 'completed'
  | 'cancel_requested'
  | 'cancelled'
  | 'detached'
  | 'unknown'
  | 'failed';
export interface Generation {
  mode: string;
  prompt: string;
  ratio: string;
  megapixels: number;
  seconds: number;
  seed: string | number;
  steps: number;
  cinema: boolean;
  cinema_strength: number;
  quad_lora: boolean;
  qwen_int8: boolean;
  edit_follow_source?: boolean;
  styles: string[];
  scale: number;
  references: string[];
  api_model?: string;
  api_resolution?: string;
  api_watermark?: boolean;
  api_context_ir?: boolean;
  api_last_frame?: boolean;
  video_references?: string[];
}
export const isVideoMode = (mode: string) => mode.startsWith('h3') || mode.startsWith('pixstag_');
export interface Version {
  id: string;
  media: string;
  url: string;
  file: string;
  kind: 'image' | 'video';
  prompt: string;
  time: string;
  label: string;
  generation?: Generation;
  materials?: unknown[];
  error?: string;
}
export interface Asset {
  id: string;
  name: string;
  description: string;
  kind: 'characters' | 'scenes';
  versions: Version[];
  current: string;
  tags: string[];
  imageFile: string;
  needsReview: boolean;
}
export interface Shot {
  id: string;
  name: string;
  numberName: string;
  description: string;
  duration: number;
  durationLabel: string;
  assetIds: string[];
  versions: Version[];
  imageVersion: string | null;
  videoVersion: string | null;
  collapsed: boolean;
  imageFile: string;
  needsReview: boolean;
  references: { file: string; url: string }[];
}
export interface Task {
  id: string;
  targetId: string;
  targetName: string;
  kind: 'image' | 'video';
  status: Status;
  progress: number | null;
  steps: { value: number; max: number } | null;
  node: string | null;
  prompt: string;
  time: string;
  error?: string;
  generation: Generation;
  outputs: string[];
  results: Version[];
  raw: unknown;
  provider?: string;
  remoteId?: string;
  canCancel?: boolean;
  canDetach?: boolean;
}
export interface Suggestion {
  id: string;
  name: string;
  title: string;
  args: Record<string, unknown>;
  targetId?: string;
  targetName?: string;
  generation?: Generation;
}
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'tool';
  text: string;
  time: string;
  targetName?: string;
  activity: {
    type: string;
    skill?: string;
    file?: string;
    query?: string;
    sources?: { title: string; url: string }[];
    message?: string;
  }[];
}
export interface ProjectState {
  id: string;
  name: string;
  root: string;
  story: string;
  updated: string;
  assets: Asset[];
  shots: Shot[];
  tasks: Task[];
  chat: ChatMessage[];
  paused: boolean;
}
export interface MediaContext {
  file: string;
  name: string;
  kind: 'image' | 'video';
  media?: string;
}
export interface LibraryAsset extends MediaContext {
  id: string;
  media: string;
  source: 'imported' | 'generated' | 'project';
  owners: { id: string; name: string; kind: 'characters' | 'scenes' | 'shots' }[];
  versionIds: string[];
  jobs: string[];
  current: boolean;
  deletedOwner: boolean;
  prompt: string;
  time: string;
  exists: boolean;
  bytes: number | null;
  width: number | null;
  height: number | null;
  duration: number | null;
  error: string;
}
export interface LibraryResult {
  kind: 'image' | 'video';
  total: number;
  offset: number;
  limit: number;
  hasMore: boolean;
  stats: { all: number; imported: number; generated: number; project: number; missing: number };
  items: LibraryAsset[];
}
export interface State {
  version: string;
  config: { comfy: string; model: string; models: string[]; online: boolean; keySet: boolean; pixstagKeySet?: boolean };
  catalog: {
    modes: Record<string, string>;
    ratios: string[];
    styles: Record<string, string>;
    skills: unknown;
    pixstag?: { models: string[]; ratios: string[]; resolutions: string[] };
  };
  recent: { path: string; title: string }[];
  selectedId: string | null;
  contextIds: string[];
  mediaContext: MediaContext[];
  activeJob: string | null;
  busy: boolean;
  modelsBusy: boolean;
  status: string;
  error: string;
  review: Suggestion | null;
  project: ProjectState | null;
}
export type GenerationInput = Generation;
