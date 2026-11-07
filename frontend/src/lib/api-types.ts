/* GENERATED from backend OpenAPI — do not edit by hand. Run: npm run gen:api */

export interface AccessRequestCreate {
  username: string;
  password: string;
  message?: string | null;
}

export interface AccessRequestOut {
  id: string;
  username: string;
  status: string;
}

export interface ArtifactOut {
  id: string;
  track_version_id: string;
  kind: string;
  mime_type: string;
  byte_size: number | null;
  sha256: string | null;
  is_external: boolean;
  external_url: string | null;
  file_name: string | null;
  language: string | null;
}

export interface ArtifactReferenceIn {
  kind: string;
  external_url: string;
  attribution?: string | null;
  language?: string | null;
  file_name?: string | null;
}

export interface Body_upload_artifact_api_v1_tracks__track_id__versions__version_id__artifacts_upload_post {
  file: string;
  kind: string;
  language?: string | null;
}

export interface CrewCreate {
  name: string;
  description?: string | null;
}

export interface CrewOut {
  id: string;
  name: string;
  description?: string | null;
}

export interface CrewTrackEntryOut {
  crew_track_id: string;
  crew_id: string;
  crew_name: string;
  requester: string | null;
  notes: string | null;
  piano_suitability: string;
  vote_score: number;
  my_vote: number | null;
}

export interface CrewTrackList {
  items: CrewTrackListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface CrewTrackListItem {
  crew_track_id: string;
  track_id: string;
  title: string | null;
  artist: string | null;
  genres: string[];
  requester: string | null;
  piano_suitability: string;
  vote_score: number;
  my_vote: number | null;
  version_count: number;
  artifact_kinds: string[];
}

export interface CrewTrackPatch {
  notes?: string | null;
  piano_suitability?: string | null;
}

export interface HTTPValidationError {
  detail?: ValidationError[];
}

export interface ImportRequest {
  provider: string;
  external_id: string;
  crew_id: string;
  track_id?: string | null;
  version_id?: string | null;
  version_label?: string | null;
  artifact_types?: string[];
  profile?: Record<string, unknown> | null;
  idempotency_key?: string | null;
}

export interface JobCreate {
  kind: string;
  payload?: Record<string, unknown>;
  crew_id?: string | null;
  idempotency_key?: string | null;
}

export interface JobList {
  items: JobOut[];
  total: number;
  limit: number;
  offset: number;
}

export interface JobOut {
  id: string;
  kind: string;
  status: string;
  crew_id: string | null;
  created_by_id: string | null;
  progress: number;
  wait_reason: string | null;
  attempts: number;
  result: Record<string, unknown> | null;
  error: string | null;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  csrf_token: string;
  user: UserOut;
}

export interface MemberAdd {
  user_id: string;
  role?: string;
}

export interface MemberOut {
  user_id: string;
  username: string;
  role: string;
}

export interface OnlineSearchRequest {
  query: string;
  providers?: string[];
  artifact_types?: string[];
  crew_id: string;
}

export interface RepresentationItem {
  artifact: ArtifactOut;
  source_provider?: string | null;
  attribution?: string | null;
  derived?: boolean;
  warnings?: string[];
}

export interface RepresentationResponse {
  context: string;
  track_id: string;
  items?: RepresentationItem[];
}

export interface SearchHitOut {
  track_id: string;
  title: string | null;
  artist: string | null;
  genres?: string[];
  snippet?: string;
  score?: number;
  source?: string;
}

export interface SearchResponse {
  items?: SearchHitOut[];
  total?: number;
  limit?: number;
  offset?: number;
}

export interface TrackDetail {
  id: string;
  title: string | null;
  artist: string | null;
  description: string | null;
  genres: string[];
  versions: VersionDetailOut[];
  crew_entries: CrewTrackEntryOut[];
}

export interface TrackPatch {
  title?: string | null;
  artist?: string | null;
  description?: string | null;
  genres?: string[] | null;
}

export interface TrackSuggest {
  title?: string | null;
  artist?: string | null;
  description?: string | null;
  genres?: string[];
  versions?: VersionCreate[];
  notes?: string | null;
  piano_suitability?: string;
}

export interface UserOut {
  id: string;
  username: string;
  display_name?: string | null;
  is_admin: boolean;
}

export interface ValidationError {
  loc: string | number[];
  msg: string;
  type: string;
  input?: unknown;
  ctx?: Record<string, unknown>;
}

export interface VersionCreate {
  label?: string | null;
  musical_key?: string | null;
  language?: string | null;
  tuning?: string | null;
  capo?: number | null;
  notes?: string | null;
}

export interface VersionDetailOut {
  label?: string | null;
  musical_key?: string | null;
  language?: string | null;
  tuning?: string | null;
  capo?: number | null;
  notes?: string | null;
  id: string;
  track_id: string;
  artifacts?: ArtifactOut[];
}

export interface VersionOut {
  label?: string | null;
  musical_key?: string | null;
  language?: string | null;
  tuning?: string | null;
  capo?: number | null;
  notes?: string | null;
  id: string;
  track_id: string;
}

export interface VoteIn {
  value: 1 | -1;
}
