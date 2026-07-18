// Shared citation-confidence logic (kept out of Citations.jsx so that file
// only exports components — react-refresh requirement).

// Fields scoring below this (on our composite metric) need human review.
export const LOW_CONFIDENCE = 0.7;

export const isLowConfidence = (cite) =>
  Boolean(cite) &&
  (cite.verified === false ||
    (cite.score !== null && cite.score !== undefined && cite.score < LOW_CONFIDENCE));
