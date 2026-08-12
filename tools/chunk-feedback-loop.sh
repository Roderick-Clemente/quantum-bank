#!/bin/bash
# tools/chunk-feedback-loop.sh
# Automate CHUNK review → feedback → executor → iterate loop
# Reviewers are the gate; loop until ACCEPT or max_turns

set -euo pipefail

FRAMEWORK_ROOT="${1:-.}"
PILOT_ROOT="${2:-.}"
CHUNK_NAME="${3:-CHUNK_0}"
MAX_TURNS="${4:-5}"

QUANTUM_STEER="$PILOT_ROOT/STEER.md"
# Convert CHUNK_0 → chunk-0-review-evidence, CHUNK_1 → chunk-1-review-evidence, etc.
CHUNK_NUM=$(echo "$CHUNK_NAME" | sed 's/CHUNK_//')
REVIEW_DIR="$PILOT_ROOT/chunk-${CHUNK_NUM}-review-evidence"

echo "🔄 Chunk Feedback Loop: $CHUNK_NAME (max $MAX_TURNS turns)"
echo "📍 Framework: $FRAMEWORK_ROOT"
echo "📍 Pilot: $PILOT_ROOT"
echo ""

turn=0
while [ $turn -lt $MAX_TURNS ]; do
  turn=$((turn + 1))
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "TURN $turn: Running validators..."
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  # Run orchestrate-review.py
  python3 "$FRAMEWORK_ROOT/tools/orchestrate-review.py" \
    --framework-root "$FRAMEWORK_ROOT" \
    --pilot-root "$PILOT_ROOT" \
    --pilot-python "$(which python3)" \
    --test-file "test/test_banking_routes.py" \
    --lock-file "phase-0/locks/test_banking_routes.lock" \
    --prompt-file <(cat <<'PROMPT'
Review the committed code diff. Does it:
- Match the approved plan?
- Preserve existing behavior?
- Pass all tests?
- Avoid circular imports?
- Have no stubs/experiment code?

Verdict: ACCEPT or REJECT with blockers.
PROMPT
) \
    --review-output-dir "$REVIEW_DIR" \
    --validators "grok-4.5:xai:grok-family,gemini-3.1-pro-preview:google:gemini-family" \
    --auto-level high || true  # Don't fail on REJECT exit

  # Parse verdicts and token usage from envelopes
  GROK_VERDICT=$(jq -r '.result' "$REVIEW_DIR/review-grok-4.5-envelope.json" 2>/dev/null | grep -o "VERDICT: [A-Z-]*" | head -1 || echo "UNKNOWN")
  GROK_TOKENS_IN=$(jq -r '.usage.input_tokens // 0' "$REVIEW_DIR/review-grok-4.5-envelope.json" 2>/dev/null || echo "0")
  GROK_TOKENS_OUT=$(jq -r '.usage.output_tokens // 0' "$REVIEW_DIR/review-grok-4.5-envelope.json" 2>/dev/null || echo "0")
  GROK_DURATION=$(jq -r '.duration_ms // 0' "$REVIEW_DIR/review-grok-4.5-envelope.json" 2>/dev/null || echo "0")

  GEMINI_VERDICT=$(jq -r '.result' "$REVIEW_DIR/review-gemini-3.1-pro-preview-envelope.json" 2>/dev/null | grep -o "VERDICT: [A-Z-]*" | head -1 || echo "UNKNOWN")
  GEMINI_TOKENS_IN=$(jq -r '.usage.input_tokens // 0' "$REVIEW_DIR/review-gemini-3.1-pro-preview-envelope.json" 2>/dev/null || echo "0")
  GEMINI_TOKENS_OUT=$(jq -r '.usage.output_tokens // 0' "$REVIEW_DIR/review-gemini-3.1-pro-preview-envelope.json" 2>/dev/null || echo "0")
  GEMINI_DURATION=$(jq -r '.duration_ms // 0' "$REVIEW_DIR/review-gemini-3.1-pro-preview-envelope.json" 2>/dev/null || echo "0")

  TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  echo ""
  echo "✓ Grok:   $GROK_VERDICT ($GROK_TOKENS_IN in / $GROK_TOKENS_OUT out)"
  echo "✓ Gemini: $GEMINI_VERDICT ($GEMINI_TOKENS_IN in / $GEMINI_TOKENS_OUT out)"
  echo ""

  # Append to RUN-LEDGER.md
  RUN_LEDGER="$PILOT_ROOT/RUN-LEDGER.md"
  if [ ! -f "$RUN_LEDGER" ]; then
    cat > "$RUN_LEDGER" <<'LEDGER_HEADER'
# Run Ledger — QuantumBank DAO Refactor

| Turn | Chunk | Model | Family | Verdict | Tokens In | Tokens Out | Duration (ms) | Timestamp |
|------|-------|-------|--------|---------|-----------|------------|---------------|-----------|
LEDGER_HEADER
  fi

  echo "| $turn | $CHUNK_NAME | grok-4.5 | xai | $GROK_VERDICT | $GROK_TOKENS_IN | $GROK_TOKENS_OUT | $GROK_DURATION | $TIMESTAMP |" >> "$RUN_LEDGER"
  echo "| $turn | $CHUNK_NAME | gemini-3.1-pro | google | $GEMINI_VERDICT | $GEMINI_TOKENS_IN | $GEMINI_TOKENS_OUT | $GEMINI_DURATION | $TIMESTAMP |" >> "$RUN_LEDGER"

  echo "📊 Telemetry logged to RUN-LEDGER.md"

  # Write STEER.md with feedback
  cat > "$QUANTUM_STEER" <<EOF
# Code Review Feedback — $CHUNK_NAME Turn $turn

**Status:** $([ "$GROK_VERDICT" == "VERDICT: ACCEPT" ] && [ "$GEMINI_VERDICT" == "VERDICT: ACCEPT" ] && echo "✅ ACCEPT" || echo "❌ REJECT")

**Reviewers:**
- Grok: $GROK_VERDICT
- Gemini: $GEMINI_VERDICT

## Required Fixes

$(jq -r '.result' "$REVIEW_DIR/review-grok-4.5-envelope.json" 2>/dev/null | head -50)

---

$(jq -r '.result' "$REVIEW_DIR/review-gemini-3.1-pro-preview-envelope.json" 2>/dev/null | head -50)

---

## Next Steps

1. Read the blockers above
2. Edit code to fix issues
3. Run: \`pytest test/ -v\` (must stay green)
4. Commit: \`git add -A && git commit --amend --no-edit\`
5. Script will re-review; loop continues

Max turns: $MAX_TURNS | Current turn: $turn

Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
EOF

  echo "📝 Feedback written to STEER.md"

  # Check if both accept
  if [ "$GROK_VERDICT" == "VERDICT: ACCEPT" ] && [ "$GEMINI_VERDICT" == "VERDICT: ACCEPT" ]; then
    echo ""
    echo "🎉 BOTH REVIEWERS ACCEPT!"
    echo "   $CHUNK_NAME is ready."
    rm "$QUANTUM_STEER"  # Clean up steering file
    exit 0
  fi

  # If max turns reached, exit
  if [ $turn -ge $MAX_TURNS ]; then
    echo ""
    echo "⚠️  MAX TURNS ($MAX_TURNS) REACHED"
    echo "   Reviewers still rejecting. Manual review needed."
    exit 1
  fi

  echo ""
  echo "⏳ Waiting for executor to fix and re-commit..."
  echo "   Once fixed, run this script again to re-review."
  echo ""

  # Optional: wait and auto-detect re-commit (requires git hook or external signal)
  sleep 5
done

exit 1
