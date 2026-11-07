/** Small navigation contract; workflow-specific state stays inside each module. */
export const addMethods = [
  { id: "manual", title: "Suggest a track", description: "Bring a song idea to your crew. Metadata can be added later.", to: "#manual", symbol: "+" },
  { id: "discovery", title: "Discover online", description: "Search available providers, then explicitly import your selection.", to: "/search", symbol: "⌕" },
  { id: "material", title: "Upload or link materials", description: "Open a track, choose a version, and attach lyrics, chords, tablature or sheet music.", to: "/", symbol: "♫" },
] as const;
