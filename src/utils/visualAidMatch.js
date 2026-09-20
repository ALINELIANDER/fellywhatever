/* Simple, dependency-free visual-aid label matcher for the Live Classroom.
   Recognized teacher text is checked word-wise (case-insensitive) against the
   stored visual-aid labels with minimal singular/plural support. No AI, no
   embeddings, no semantic similarity. */

const SPECIAL_PAIRS = [
  ["leaf", "leaves"],
  ["life", "lives"],
  ["knife", "knives"],
  ["child", "children"],
];

export function escapeRegExp(s) {
  return String(s).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function labelVariants(label) {
  const l = String(label || "").toLowerCase().trim();
  if (!l) return [];
  const variants = new Set([l]);
  if (l.endsWith("s")) {
    variants.add(l.slice(0, -1));
  } else {
    variants.add(l + "s");
    if (l.endsWith("y")) variants.add(l.slice(0, -1) + "ies");
  }
  for (const [a, b] of SPECIAL_PAIRS) {
    if (l === a) variants.add(b);
    if (l === b) variants.add(a);
  }
  return [...variants];
}

export function textMentionsLabel(text, label) {
  const t = String(text || "").toLowerCase();
  if (!t) return false;
  return labelVariants(label).some((variant) => {
    const re = new RegExp(`(^|[^\\p{L}\\p{N}])${escapeRegExp(variant)}([^\\p{L}\\p{N}]|$)`, "iu");
    return re.test(t);
  });
}

/* Walk the transcript from the most recent utterance back to the oldest and
   return the visual aid whose label is mentioned, preferring the newest
   mention. Returns null when nothing matches. */
export function latestVisualAidMatch(transcript, aids) {
  if (!transcript || !transcript.length || !aids || !aids.length) return null;
  for (let i = transcript.length - 1; i >= 0; i--) {
    const text = String(transcript[i].hindi || "");
    if (!text.trim()) continue;
    for (const aid of aids) {
      const label = String(aid.label || "").toLowerCase().trim();
      if (!label) continue;
      if (textMentionsLabel(text, label)) return aid;
    }
  }
  return null;
}