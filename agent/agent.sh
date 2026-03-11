#!/usr/bin/env bash
# MQE Improvement Agent — Orchestrator
#
# Autonomous loop: analyze → change → validate → full run → promote/rollback
# Calls Claude Code per iteration for analysis and decision-making.
#
# Usage: cd mqe && ./agent/agent.sh [--dry-run]
set -euo pipefail

AGENT_DIR="$(cd "$(dirname "$0")" && pwd)"
MQE_DIR="$(dirname "$AGENT_DIR")"
RESULTS_DIR="$MQE_DIR/results"
LOGS_DIR="$AGENT_DIR/logs"

MAX_ITERATIONS=30
MAX_HOURS=72
SCORE_MARGIN=1.0
CORE_PAIRS="BTC/USDT ETH/USDT SOL/USDT"

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

# ── Colors ───────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'
BLUE='\033[0;34m'; NC='\033[0m'

log_info()  { echo -e "${BLUE}[AGENT]${NC} $*"; }
log_ok()    { echo -e "${GREEN}[AGENT]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[AGENT]${NC} $*"; }
log_error() { echo -e "${RED}[AGENT]${NC} $*"; }

# ── Caffeinate ───────────────────────────────────────────────────────
ensure_caffeinate() {
    if [[ -z "${CAFFEINATE_PID:-}" ]]; then
        caffeinate -i -s &
        CAFFEINATE_PID=$!
        log_info "caffeinate started (PID $CAFFEINATE_PID)"
    fi
}

# ── Single Instance ──────────────────────────────────────────────────
check_single_instance() {
    local pidfile="$AGENT_DIR/agent.pid"
    if [[ -f "$pidfile" ]]; then
        local old_pid
        old_pid=$(cat "$pidfile")
        if kill -0 "$old_pid" 2>/dev/null; then
            log_error "Agent already running (PID $old_pid). Exiting."
            exit 1
        fi
    fi
    echo $$ > "$pidfile"
}

# ── Cleanup ──────────────────────────────────────────────────────────
cleanup() {
    [[ -n "${CAFFEINATE_PID:-}" ]] && kill "$CAFFEINATE_PID" 2>/dev/null || true
    rm -f "$AGENT_DIR/agent.pid"
    log_info "Agent cleanup complete."
}
trap cleanup EXIT

# ── State Management ─────────────────────────────────────────────────
get_state() {
    python3 -c "
import json, sys
state = json.load(open('$AGENT_DIR/state.json'))
print(state.get('$1', '$2'))
"
}

set_state() {
    python3 "$AGENT_DIR/resilience.py" write-state "$1" "$2"
}

get_iteration()     { get_state "iteration" "0"; }
get_level()         { get_state "level" "L1"; }
get_best_score()    { get_state "best_score" "0"; }
get_best_run()      { get_state "best_run" ""; }
get_phase()         { get_state "phase" "deciding"; }
get_no_improvement(){ get_state "consecutive_no_improvement" "0"; }

# ── History ──────────────────────────────────────────────────────────
init_history() {
    [[ -f "$AGENT_DIR/history.json" ]] || echo "[]" > "$AGENT_DIR/history.json"
}

append_history() {
    # Write entry to temp file to avoid shell injection in triple-quoted strings
    local entry="$1"
    local tmpfile
    tmpfile=$(mktemp)
    printf '%s' "$entry" > "$tmpfile"
    python3 -c "
import json, sys
with open('$tmpfile') as f:
    entry = json.load(f)
history = json.load(open('$AGENT_DIR/history.json'))
history.append(entry)
with open('$AGENT_DIR/history.json', 'w') as f:
    json.dump(history, f, indent=2)
"
    rm -f "$tmpfile"
}

# ── Git Operations ───────────────────────────────────────────────────
init_git() {
    cd "$MQE_DIR"
    if git show-ref --verify --quiet refs/heads/agent/best 2>/dev/null; then
        log_info "Branch agent/best already exists, checking out."
        git checkout agent/best
    else
        log_info "Creating agent/best from current HEAD."
        git checkout -b agent/best
    fi
}

create_iter_branch() {
    local iter=$1
    local branch
    branch=$(printf "agent/iter-%03d" "$iter")
    cd "$MQE_DIR"
    git checkout -b "$branch"
    set_state "current_branch" "$branch"
    log_info "Created branch $branch"
}

promote_to_best() {
    local iter=$1
    local branch
    branch=$(printf "agent/iter-%03d" "$iter")
    cd "$MQE_DIR"
    git checkout agent/best
    git merge "$branch" --no-edit -m "agent: promote iter $iter to best"
    set_state "current_branch" "agent/best"
    log_ok "Promoted $branch → agent/best"
}

rollback_to_best() {
    cd "$MQE_DIR"
    git checkout agent/best
    set_state "current_branch" "agent/best"
    log_warn "Rolled back to agent/best"
}

cleanup_old_branches() {
    local current_iter=$1
    local cutoff=$((current_iter - 10))
    [[ $cutoff -lt 1 ]] && return
    cd "$MQE_DIR"
    for i in $(seq 1 "$cutoff"); do
        local branch
        branch=$(printf "agent/iter-%03d" "$i")
        if git show-ref --verify --quiet "refs/heads/$branch" 2>/dev/null; then
            git branch -D "$branch" 2>/dev/null || true
        fi
    done
}

# ── Discord Notifications ────────────────────────────────────────────
load_webhook() {
    if [[ -f "$MQE_DIR/.env" ]]; then
        DISCORD_WEBHOOK=$(grep -E '^DISCORD_WEBHOOK_MQE_RUNS=' "$MQE_DIR/.env" \
            | cut -d'=' -f2- | tr -d '"' | tr -d "'")
    fi
    DISCORD_WEBHOOK="${DISCORD_WEBHOOK:-}"
}

send_discord() {
    local message="$1"
    [[ -z "$DISCORD_WEBHOOK" ]] && return 0
    # Use stdin to avoid shell injection in triple-quoted strings
    local payload
    payload=$(printf '%s' "$message" | python3 -c "
import json, sys
msg = sys.stdin.read()
print(json.dumps({'content': '\`\`\`\n' + msg + '\n\`\`\`'}))
")
    curl -s -X POST -H "Content-Type: application/json" \
        -d "$payload" "$DISCORD_WEBHOOK" > /dev/null 2>&1 || true
}

send_iteration_notification() {
    local iter=$1 level=$2 change="$3" val_info="$4" full_info="$5"
    local result=$6 best_score=$7 calmar=$8 dd=$9 pairs=${10}
    local msg
    msg=$(printf "MQE AGENT — Iteration %d (%s)\n" "$iter" "$level")
    msg+="=============================="$'\n'
    msg+="Change: $change"$'\n'
    [[ -n "$val_info" ]] && msg+="Valid:  $val_info"$'\n'
    [[ -n "$full_info" ]] && msg+="Full:   $full_info"$'\n'
    msg+="Best:   $best_score (iter $iter)"$'\n'
    msg+="──────────────────────────────"$'\n'
    msg+="Calmar=$calmar  DD=$dd  Pairs=$pairs"
    send_discord "$msg"
}

send_stop_notification() {
    local reason="$1" best_score="$2" best_iter="$3"
    local total_iter="$4" promotes="$5" rollbacks="$6"
    local duration="$7"
    local msg
    if [[ "$reason" == "top_achieved" ]]; then
        msg="MQE AGENT — COMPLETED ★"$'\n'
    else
        msg="MQE AGENT — STOPPED"$'\n'
    fi
    msg+="=============================="$'\n'
    msg+="Reason: $reason"$'\n'
    msg+="Best:   Score $best_score (iter $best_iter)"$'\n'
    msg+="──────────────────────────────"$'\n'
    msg+="Iterations: $total_iter ($promotes promote, $rollbacks rollback)"$'\n'
    msg+="Duration:   $duration"
    send_discord "$msg"
}

# ── NOTES.md ─────────────────────────────────────────────────────────
append_notes() {
    local iter=$1 level=$2 change="$3" reason="$4"
    local files="$5" val_info="$6" full_info="$7" decision="$8"
    local timestamp
    timestamp=$(date "+%Y-%m-%d %H:%M")

    cat >> "$MQE_DIR/NOTES.md" << EOF

## Agent Iteration $iter — $timestamp ($level)

**Change:** $change
**Reason:** $reason
**Files:** $files
**Validation:** $val_info
**Full run:** $full_info
**Decision:** $decision
EOF
}

# ── MQE Run Management ──────────────────────────────────────────────
find_latest_results() {
    # Find most recent results directory
    ls -td "$RESULTS_DIR"/*/ 2>/dev/null | head -1
}

run_mqe_validation() {
    local run_mode="$1" iter=$2
    cd "$MQE_DIR"

    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] Would run validation ($run_mode)"
        return 0
    fi

    local tag="agent-iter-${iter}-val"
    if [[ "$run_mode" == "resume_s2" ]]; then
        local best_run
        best_run=$(get_best_run)
        log_info "Running validation: resume S2 from $best_run"
        ./run.sh resume "$best_run" --s2-trials 500 --tag "$tag"
    elif [[ "$run_mode" == "core_pairs" ]]; then
        log_info "Running validation: 3 core pairs"
        ./run.sh --symbols $CORE_PAIRS --s2-trials 500 --fg --tag "$tag"
    fi
}

run_mqe_full() {
    local iter=$1
    cd "$MQE_DIR"

    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] Would run full optimization"
        return 0
    fi

    local tag="agent-iter-${iter}-full"
    log_info "Running full optimization (20 pairs)..."
    ./run.sh --fg --tag "$tag"
}

compute_score() {
    local results_dir="$1"
    python3 "$AGENT_DIR/resilience.py" compute-score "$results_dir"
}

# ── Claude Code Invocation ───────────────────────────────────────────
call_claude() {
    local task_type="$1"
    shift
    local extra_args=("$@")

    mkdir -p "$LOGS_DIR"
    local iter
    iter=$(get_iteration)
    local prompt_file="/tmp/mqe-agent-prompt-${iter}-${task_type}.md"
    local log_file="$LOGS_DIR/claude_iter_${iter}_${task_type}.log"

    # Build prompt
    local extra=""
    for arg in "${extra_args[@]+"${extra_args[@]}"}"; do
        extra+=" $arg"
    done
    python3 "$AGENT_DIR/build_prompt.py" "$task_type" $extra > "$prompt_file"

    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] Would call Claude Code with task: $task_type"
        log_info "[DRY RUN] Prompt saved to: $prompt_file"
        # Write stub decision.json so the loop can proceed
        echo '{"action":"stop","stop_reason":"dry_run_complete"}' > "$AGENT_DIR/decision.json"
        return 0
    fi

    log_info "Calling Claude Code (task: $task_type)..."
    # Remove old decision.json to detect if Claude writes a new one
    rm -f "$AGENT_DIR/decision.json"

    cd "$MQE_DIR"
    claude -p "$(cat "$prompt_file")" \
        --max-turns 50 \
        2>&1 | tee "$log_file"

    if [[ ! -f "$AGENT_DIR/decision.json" ]]; then
        log_error "Claude did not write decision.json"
        return 1
    fi

    log_ok "Claude Code completed. Decision written."
}

read_decision() {
    local field="$1"
    local default="${2:-}"
    python3 -c "
import json
d = json.load(open('$AGENT_DIR/decision.json'))
print(d.get('$field', '$default'))
"
}

# ── Time Tracking ────────────────────────────────────────────────────
elapsed_hours() {
    python3 -c "
import json, time
state = json.load(open('$AGENT_DIR/state.json'))
elapsed = (time.time() - state['start_time']) / 3600
print(f'{elapsed:.1f}')
"
}

format_duration() {
    python3 -c "
import json, time
state = json.load(open('$AGENT_DIR/state.json'))
secs = time.time() - state['start_time']
hours = int(secs // 3600)
days = hours // 24
remaining_hours = hours % 24
if days > 0:
    print(f'{days}d {remaining_hours}h')
else:
    print(f'{hours}h')
"
}

# ── Escalation Logic ────────────────────────────────────────────────
check_escalation() {
    local no_improvement
    no_improvement=$(get_no_improvement)
    local current_level
    current_level=$(get_level)

    if [[ "$no_improvement" -ge 2 ]]; then
        case "$current_level" in
            L1)
                set_state "level" "L2"
                set_state "consecutive_no_improvement" "0"
                log_warn "Escalating L1 → L2 (2 iterations without improvement)"
                ;;
            L2)
                set_state "level" "L3"
                set_state "consecutive_no_improvement" "0"
                log_warn "Escalating L2 → L3 (2 iterations without improvement)"
                ;;
            L3)
                # L3 + 2 no improvement = plateau exhaustion
                return 1  # Signal stop
                ;;
        esac
    fi
    return 0
}

# ── Pytest Gate ──────────────────────────────────────────────────────
run_pytest() {
    cd "$MQE_DIR"
    log_info "Running pytest..."
    if uv run pytest tests/ -x -q 2>&1; then
        log_ok "Tests passed."
        return 0
    else
        log_error "Tests FAILED."
        return 1
    fi
}

# ── Final Report ─────────────────────────────────────────────────────
generate_final_report() {
    local best_score best_run total_iter promotes rollbacks duration
    best_score=$(get_best_score)
    best_run=$(get_best_run)
    total_iter=$(get_iteration)
    promotes=$(get_state "total_promotes" "0")
    rollbacks=$(get_state "total_rollbacks" "0")
    duration=$(format_duration)

    python3 -c "
import json
from pathlib import Path

agent_dir = Path('$AGENT_DIR')
history = json.load(open(agent_dir / 'history.json'))

# Promoted changes
promoted = [e for e in history if e.get('result') == 'promote']
failed = [e for e in history if e.get('result') == 'rollback']

report = []
report.append('# MQE Agent — Final Report')
report.append('')
report.append(f'**Duration:** $duration')
report.append(f'**Iterations:** $total_iter ($promotes promote, $rollbacks rollback)')
report.append(f'**Best Score:** $best_score')
report.append(f'**Best Run:** $best_run')
report.append('')
report.append('## Changes in agent/best')
report.append('')
for e in promoted:
    report.append(f\"- Iter {e['iteration']} ({e['level']}): {e['change_description']} (score: {e.get('score', 'N/A')})\")
report.append('')
report.append('## Failed Attempts (lessons learned)')
report.append('')
for e in failed:
    report.append(f\"- Iter {e['iteration']} ({e['level']}): {e['change_description']} — {e.get('reasoning', 'N/A')}\")

(agent_dir / 'FINAL_REPORT.md').write_text('\n'.join(report) + '\n')
print('Final report written to agent/FINAL_REPORT.md')
"
}

# ── Main Loop ────────────────────────────────────────────────────────
main() {
    log_info "═══════════════════════════════════════"
    log_info "  MQE Improvement Agent Starting"
    log_info "═══════════════════════════════════════"

    # Pre-checks
    check_single_instance
    ensure_caffeinate
    load_webhook
    mkdir -p "$LOGS_DIR"

    cd "$MQE_DIR"

    # Check for crash recovery
    if [[ -f "$AGENT_DIR/state.json" ]]; then
        local phase
        phase=$(get_phase)
        if [[ "$phase" != "deciding" && "$phase" != "decided" ]]; then
            log_warn "Recovering from crash (phase: $phase)"
            # Reset to deciding — simplest recovery
            set_state "phase" "deciding"
            rollback_to_best
        else
            log_info "Resuming from iteration $(get_iteration)"
        fi
    else
        # Fresh start
        init_git
        init_history
        python3 "$AGENT_DIR/resilience.py" init-state

        # Run baseline
        log_info "Running baseline optimization..."
        if [[ "$DRY_RUN" != true ]]; then
            ./run.sh --fg --tag "agent-baseline"
            local baseline_dir
            baseline_dir=$(find_latest_results)
            local baseline_result
            baseline_result=$(compute_score "$baseline_dir")
            local baseline_score
            baseline_score=$(echo "$baseline_result" | python3 -c "import json,sys; print(json.load(sys.stdin)['score'])")

            set_state "best_run" "$baseline_dir"
            set_state "best_score" "$baseline_score"
            log_ok "Baseline Score: $baseline_score"
            send_discord "MQE AGENT — STARTED\n==============================\nBaseline: Score $baseline_score\nMode: Autonomous improvement\nMax: $MAX_ITERATIONS iters / ${MAX_HOURS}h"
        else
            set_state "best_score" "50.0"
            set_state "best_run" "results/dry-run-baseline"
            log_info "[DRY RUN] Baseline skipped, using score 50.0"
        fi
    fi

    # Main iteration loop
    while true; do
        local iter
        iter=$(($(get_iteration) + 1))
        set_state "iteration" "$iter"
        set_state "phase" "deciding"

        log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        log_info "  Iteration $iter ($(get_level))"
        log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

        # Check hard caps
        local hours_elapsed
        hours_elapsed=$(elapsed_hours)
        if (( $(echo "$hours_elapsed >= $MAX_HOURS" | bc -l) )); then
            log_warn "Time limit reached (${hours_elapsed}h / ${MAX_HOURS}h)"
            generate_final_report
            send_stop_notification "time_limit" "$(get_best_score)" "$(get_iteration)" \
                "$iter" "$(get_state total_promotes 0)" "$(get_state total_rollbacks 0)" \
                "$(format_duration)"
            break
        fi
        if [[ $iter -gt $MAX_ITERATIONS ]]; then
            log_warn "Max iterations reached ($MAX_ITERATIONS)"
            generate_final_report
            send_stop_notification "max_iterations" "$(get_best_score)" "$(get_iteration)" \
                "$iter" "$(get_state total_promotes 0)" "$(get_state total_rollbacks 0)" \
                "$(format_duration)"
            break
        fi

        # Check escalation
        if ! check_escalation; then
            log_warn "Plateau exhaustion at L3"
            generate_final_report
            send_stop_notification "plateau_exhaustion" "$(get_best_score)" "$(get_iteration)" \
                "$iter" "$(get_state total_promotes 0)" "$(get_state total_rollbacks 0)" \
                "$(format_duration)"
            break
        fi

        # Create iteration branch
        create_iter_branch "$iter"

        # ── Step 1: Call Claude to decide + implement ──
        set_state "phase" "deciding"
        if ! call_claude "decide"; then
            log_error "Claude Code failed. Retrying once..."
            if ! call_claude "decide"; then
                log_error "Claude Code failed twice. Stopping."
                generate_final_report
                send_stop_notification "claude_error" "$(get_best_score)" "$(get_iteration)" \
                    "$iter" "$(get_state total_promotes 0)" "$(get_state total_rollbacks 0)" \
                    "$(format_duration)"
                break
            fi
        fi

        local action
        action=$(read_decision "action" "implement")

        if [[ "$action" == "stop" ]]; then
            local stop_reason
            stop_reason=$(read_decision "stop_reason" "agent_decision")
            log_ok "Agent decided to stop: $stop_reason"
            generate_final_report
            send_stop_notification "$stop_reason" "$(get_best_score)" "$(get_iteration)" \
                "$iter" "$(get_state total_promotes 0)" "$(get_state total_rollbacks 0)" \
                "$(format_duration)"
            break
        fi

        local change_desc level run_mode
        change_desc=$(read_decision "change_description" "unknown change")
        level=$(read_decision "level" "L1")
        run_mode=$(read_decision "run_mode" "core_pairs")

        log_info "Change: $change_desc"
        log_info "Level: $level, Run mode: $run_mode"

        # ── Pytest gate for L2/L3 ──
        if [[ "$level" == "L2" || "$level" == "L3" ]]; then
            if ! run_pytest; then
                log_error "Pytest failed after $level change. Rolling back."
                rollback_to_best
                append_history "{\"iteration\":$iter,\"level\":\"$level\",\"change_description\":\"$change_desc\",\"result\":\"rollback\",\"reasoning\":\"pytest failed\"}"
                set_state "consecutive_no_improvement" "$(($(get_no_improvement) + 1))"
                set_state "total_rollbacks" "$(($(get_state total_rollbacks 0) + 1))"
                continue
            fi
        fi

        # ── Step 2: Run validation ──
        set_state "phase" "running_validation"
        if ! run_mqe_validation "$run_mode" "$iter"; then
            log_error "Validation run crashed. Rolling back."
            local crashes=$(($(get_state consecutive_crashes 0) + 1))
            set_state "consecutive_crashes" "$crashes"
            if [[ $crashes -ge 3 ]]; then
                log_error "3 consecutive crashes. Stopping."
                generate_final_report
                send_stop_notification "repeated_crashes" "$(get_best_score)" "$(get_iteration)" \
                    "$iter" "$(get_state total_promotes 0)" "$(get_state total_rollbacks 0)" \
                    "$(format_duration)"
                break
            fi
            rollback_to_best
            append_history "{\"iteration\":$iter,\"level\":\"$level\",\"change_description\":\"$change_desc\",\"result\":\"rollback\",\"reasoning\":\"validation run crashed\"}"
            set_state "consecutive_no_improvement" "$(($(get_no_improvement) + 1))"
            set_state "total_rollbacks" "$(($(get_state total_rollbacks 0) + 1))"
            continue
        fi

        set_state "consecutive_crashes" "0"

        local val_dir
        val_dir=$(find_latest_results)

        # ── Step 3: Evaluate validation ──
        set_state "phase" "evaluating_validation"
        if ! call_claude "evaluate_val" "VAL_RUN_DIR=$val_dir"; then
            log_error "Claude evaluation failed. Rolling back."
            rollback_to_best
            continue
        fi

        local val_action
        val_action=$(read_decision "action" "rollback")

        if [[ "$val_action" == "rollback" ]]; then
            log_warn "Validation rejected: $change_desc"
            rollback_to_best
            append_history "{\"iteration\":$iter,\"level\":\"$level\",\"change_description\":\"$change_desc\",\"result\":\"rollback\",\"reasoning\":\"validation rejected\"}"
            set_state "consecutive_no_improvement" "$(($(get_no_improvement) + 1))"
            set_state "total_rollbacks" "$(($(get_state total_rollbacks 0) + 1))"
            append_notes "$iter" "$level" "$change_desc" "Validation rejected" \
                "$(read_decision files_changed '')" "Rejected" "N/A" "✗ ROLLBACK"
            send_iteration_notification "$iter" "$level" "$change_desc" \
                "Rejected" "N/A" "ROLLBACK" "$(get_best_score)" "N/A" "N/A" "N/A"
            continue
        fi

        # ── Step 4: Run full optimization ──
        set_state "phase" "running_full"
        if ! run_mqe_full "$iter"; then
            log_error "Full run crashed. Rolling back."
            rollback_to_best
            append_history "{\"iteration\":$iter,\"level\":\"$level\",\"change_description\":\"$change_desc\",\"result\":\"rollback\",\"reasoning\":\"full run crashed\"}"
            set_state "consecutive_no_improvement" "$(($(get_no_improvement) + 1))"
            set_state "total_rollbacks" "$(($(get_state total_rollbacks 0) + 1))"
            continue
        fi

        local full_dir
        full_dir=$(find_latest_results)

        # ── Step 5: Evaluate full run ──
        set_state "phase" "evaluating_full"
        if ! call_claude "evaluate_full" "FULL_RUN_DIR=$full_dir"; then
            log_error "Claude full evaluation failed. Rolling back."
            rollback_to_best
            continue
        fi

        local full_action
        full_action=$(read_decision "action" "rollback")
        local full_score
        full_score=$(compute_score "$full_dir" | python3 -c "import json,sys; print(json.load(sys.stdin)['score'])")

        set_state "phase" "decided"

        if [[ "$full_action" == "promote" ]]; then
            promote_to_best "$iter"
            set_state "best_score" "$full_score"
            set_state "best_run" "$full_dir"
            set_state "consecutive_no_improvement" "0"
            set_state "consecutive_crashes" "0"
            set_state "total_promotes" "$(($(get_state total_promotes 0) + 1))"
            append_history "{\"iteration\":$iter,\"level\":\"$level\",\"change_description\":\"$change_desc\",\"result\":\"promote\",\"score\":$full_score}"
            log_ok "PROMOTED! Score: $full_score"

            # Extract metrics for notification
            local calmar dd pairs
            calmar=$(python3 -c "import json; d=json.load(open('$full_dir/evaluation/portfolio_metrics.json')); print(f\"{d['calmar_ratio']:.1f}\")")
            dd=$(python3 -c "import json; d=json.load(open('$full_dir/evaluation/portfolio_metrics.json')); print(f\"{d['portfolio_max_drawdown']*100:.1f}%\")")
            pairs=$(python3 -c "import json; t=json.load(open('$full_dir/pipeline_result.json'))['tier_assignments']; print(f\"{sum(1 for v in t.values() if v['tier']!='X')}/{len(t)}\")")

            append_notes "$iter" "$level" "$change_desc" \
                "$(read_decision reasoning '')" \
                "$(read_decision files_changed '')" \
                "Promising" \
                "Score $full_score, Calmar=$calmar, DD=-$dd, $pairs pairs" \
                "✓ PROMOTE (best $(get_best_score))"
            send_iteration_notification "$iter" "$level" "$change_desc" \
                "Promising" "Score $full_score ✓ PROMOTE" "PROMOTE" \
                "$full_score" "$calmar" "-$dd" "$pairs"

        elif [[ "$full_action" == "stop" ]]; then
            local stop_reason
            stop_reason=$(read_decision "stop_reason" "agent_decision")
            # Promote this last result if it's better
            local best_score
            best_score=$(get_best_score)
            if (( $(echo "$full_score > $best_score + $SCORE_MARGIN" | bc -l) )); then
                promote_to_best "$iter"
                set_state "best_score" "$full_score"
                set_state "best_run" "$full_dir"
            fi
            generate_final_report
            send_stop_notification "$stop_reason" "$(get_best_score)" "$(get_iteration)" \
                "$iter" "$(get_state total_promotes 0)" "$(get_state total_rollbacks 0)" \
                "$(format_duration)"
            break

        else
            # Rollback
            rollback_to_best
            set_state "consecutive_no_improvement" "$(($(get_no_improvement) + 1))"
            set_state "total_rollbacks" "$(($(get_state total_rollbacks 0) + 1))"
            append_history "{\"iteration\":$iter,\"level\":\"$level\",\"change_description\":\"$change_desc\",\"result\":\"rollback\",\"score\":$full_score,\"reasoning\":\"score not improved\"}"
            log_warn "ROLLBACK. Score: $full_score (best: $(get_best_score))"
            append_notes "$iter" "$level" "$change_desc" \
                "$(read_decision reasoning '')" \
                "$(read_decision files_changed '')" \
                "Promising" \
                "Score $full_score — not better than best $(get_best_score)" \
                "✗ ROLLBACK"
            send_iteration_notification "$iter" "$level" "$change_desc" \
                "Promising" "Score $full_score ✗ ROLLBACK" "ROLLBACK" \
                "$(get_best_score)" "N/A" "N/A" "N/A"
        fi

        # Cleanup old branches
        cleanup_old_branches "$iter"
    done

    log_info "═══════════════════════════════════════"
    log_info "  MQE Improvement Agent Finished"
    log_info "═══════════════════════════════════════"
}

main "$@"
