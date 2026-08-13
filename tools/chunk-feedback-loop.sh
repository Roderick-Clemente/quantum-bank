#!/bin/bash
# tools/chunk-feedback-loop.sh
# Automate CHUNK review → feedback → executor → iterate loop
# Reviewers are the gate; single turn per invocation (executor controls loop)

set -euo pipefail

FRAMEWORK_ROOT="${1:-.}"
PILOT_ROOT="${2:-.}"
CHUNK_NAME="${3:-CHUNK_0}"

QUANTUM_STEER="$PILOT_ROOT/STEER.md"
EXECUTOR_SIGNAL="$PILOT_ROOT/.EXECUTOR-SIGNAL"

# Convert CHUNK_0 → chunk-0-review-evidence, CHUNK_1 → chunk-1-review-evidence, etc.
CHUNK_NUM=$(echo "$CHUNK_NAME" | sed 's/CHUNK_//')
REVIEW_DIR="$PILOT_ROOT/chunk-${CHUNK_NUM}-review-evidence"

echo "🔄 Single Review Turn: $CHUNK_NAME"
echo "📍 Framework: $FRAMEWORK_ROOT"
echo "📍 Pilot: $PILOT_ROOT"
echo ""

# Create review directory
mkdir -p "$REVIEW_DIR"
PROMPT_FILE="$REVIEW_DIR/review-prompt.md"

# The orchestrator launches each validator in a child process. A process-
# substitution path is not durable across that boundary, so stage the prompt
# as a normal review artifact.
cat > "$PROMPT_FILE" <<'PROMPT'
Review the committed code diff. Does it:
- Match the approved plan?
- Preserve existing behavior?
- Pass all tests?
- Avoid circular imports?
- Have no stubs/experiment code?

You MUST end your response with one of these lines:
VERDICT: ACCEPT
VERDICT: REJECT

Do not use other wording for the verdict.
PROMPT

# Single turn (executor controls loop)
turn=1

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Running validators in $PILOT_ROOT..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Run orchestrate-review.py with correct CWD
python3 "$FRAMEWORK_ROOT/tools/orchestrate-review.py" \
  --framework-root "$FRAMEWORK_ROOT" \
  --pilot-root "$PILOT_ROOT" \
  --pilot-python "$(which python3)" \
  --validator-cwd "$PILOT_ROOT" \
  --test-file "test/test_banking_routes.py" \
  --lock-file "phase-0/locks/test_banking_routes.lock" \
  --prompt-file "$PROMPT_FILE" \
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

  # Initialize or append to STEER.md
  if [ ! -f "$QUANTUM_STEER" ]; then
    cat > "$QUANTUM_STEER" <<EOF
# Code Review — $CHUNK_NAME

Verdicts and feedback from independent reviewers.

---
EOF
  fi

  # Append verdict for this turn
  cat >> "$QUANTUM_STEER" <<EOF

## Turn 1 Verdict

**Status:** $([ "$GROK_VERDICT" == "VERDICT: ACCEPT" ] && [ "$GEMINI_VERDICT" == "VERDICT: ACCEPT" ] && echo "✅ ACCEPT" || echo "❌ REJECT")

**Reviewers:**
- Grok: $GROK_VERDICT ($GROK_TOKENS_IN in / $GROK_TOKENS_OUT out)
- Gemini: $GEMINI_VERDICT ($GEMINI_TOKENS_IN in / $GEMINI_TOKENS_OUT out)

### Grok Findings
$(jq -r '.result' "$REVIEW_DIR/review-grok-4.5-envelope.json" 2>/dev/null | head -60)

### Gemini Findings
$(jq -r '.result' "$REVIEW_DIR/review-gemini-3.1-pro-preview-envelope.json" 2>/dev/null | head -60)

---

Generated: $TIMESTAMP
EOF

  echo "📝 Verdict appended to STEER.md"
  echo "📊 Telemetry logged to RUN-LEDGER.md"

  # Check if both accept
  if [ "$GROK_VERDICT" == "VERDICT: ACCEPT" ] && [ "$GEMINI_VERDICT" == "VERDICT: ACCEPT" ]; then
    echo ""
    echo "✅ BOTH REVIEWERS ACCEPT!"
    echo "   $CHUNK_NAME ready for next phase."
    echo "   Executor: delete .EXECUTOR-SIGNAL and commit CHUNK_$((CHUNK_NUM + 1))"
    touch "$EXECUTOR_SIGNAL"
    exit 0
  fi

  # If rejected, signal executor to read feedback
  echo ""
  echo "❌ REVIEWERS REJECTED $CHUNK_NAME"
  echo "   Read STEER.md for blockers."
  echo "   Fix code, amend commit, then re-run this script."
  touch "$EXECUTOR_SIGNAL"
  exit 1
