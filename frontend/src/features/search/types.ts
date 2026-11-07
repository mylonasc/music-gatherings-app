export interface SearchHit {
  provider: string;
  external_id: string;
  title: string | null;
  artist: string | null;
  artifact_types: string[];
  source_url: string | null;
  attribution: string | null;
  warnings?: string[];
}
