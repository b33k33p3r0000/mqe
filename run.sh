#!/usr/bin/env bash
# MQE Run Script — Multi-pair Quant Engine Optimizer
# Usage: ./run.sh [options]   or   ./run.sh attach|kill|logs
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# =============================================================================
# CONSTANTS
# =============================================================================

CORE_PAIRS="BTC/USDT ETH/USDT SOL/USDT"
ALL_PAIRS="BTC/USDT ETH/USDT SOL/USDT XRP/USDT BNB/USDT LINK/USDT SUI/USDT AVAX/USDT ADA/USDT NEAR/USDT LTC/USDT APT/USDT ARB/USDT OP/USDT INJ/USDT"

# =============================================================================
# HELP
# =============================================================================

show_help() {
    cat << 'EOF'
MQE Optimizer — Multi-pair Quant Engine
========================================

Presets (interactive menu when no CLI args):
  1) Test     —  1k S1 +  500 S2 trials, 3 pairs (BTC, ETH, SOL)
  2) Quick    —  5k S1 +   2k S2 trials, 3 pairs
  3) Main     — 10k S1 +   5k S2 trials, 3 pairs
  4) Full     — 10k S1 +   5k S2 trials, 15 pairs (all clusters)
  5) Custom   — You choose everything

All presets use --hours 8760 (~1yr) by default.
All runs start in background by default (use --fg for foreground).

Options:
  --s1-trials N          Stage 1 trials per pair (default: 10000)
  --s2-trials N          Stage 2 portfolio trials (default: 5000)
  --hours N              History length in hours (default: 8760)
  --tag NAME             Run tag (e.g. 'test-v1')
  --workers N            Max parallel workers
  --symbols SYM1 SYM2    Override symbol list
  --fg                   Run in foreground (default: background)

Examples:
  ./run.sh                               # Interactive preset menu
  ./run.sh --s1-trials 1000 --s2-trials 500 --fg   # Quick test, foreground
  ./run.sh --tag main-run                # Background with tag
  ./run.sh --symbols BTC/USDT SOL/USDT   # Specific pairs

Process management:
  ./run.sh attach          Attach to running/latest log
  ./run.sh kill            Kill running MQE process
  ./run.sh logs            List recent log files

EOF
}

# =============================================================================
# DEFAULTS
# =============================================================================

S1_TRIALS=""
S2_TRIALS=""
HOURS=""
TAG=""
WORKERS=""
FOREGROUND=false
SYMBOLS_OVERRIDE=""
PRESET=""
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

# =============================================================================
# PROCESS MANAGEMENT (attach, kill, logs) — parsed first
# =============================================================================

if [[ $# -gt 0 ]]; then
    case "$1" in
        attach)
            # Find actively written logs (modified in last 5 min)
            ACTIVE_LOGS=()
            while IFS= read -r f; do
                ACTIVE_LOGS+=("$f")
            done < <(find "$LOG_DIR" -name "*.log" -mmin -5 -type f 2>/dev/null | sort -r)

            if [ ${#ACTIVE_LOGS[@]} -eq 0 ]; then
                LATEST=$(ls -t "$LOG_DIR"/*.log 2>/dev/null | head -1 || true)
                if [ -z "$LATEST" ]; then
                    echo "No log files found in $LOG_DIR"
                    exit 1
                fi
                echo "No active runs. Showing latest log:"
                echo "  $(basename "$LATEST")"
                echo "(Ctrl+C to detach)"
                echo ""
                tail -f "$LATEST"
            elif [ ${#ACTIVE_LOGS[@]} -eq 1 ]; then
                echo "Attaching to: $(basename "${ACTIVE_LOGS[0]}")"
                echo "(Ctrl+C to detach — run continues in background)"
                echo ""
                tail -f "${ACTIVE_LOGS[0]}"
            else
                echo "Multiple active runs detected:"
                echo ""
                for i in "${!ACTIVE_LOGS[@]}"; do
                    LOG_NAME=$(basename "${ACTIVE_LOGS[$i]}")
                    LAST_LINE=$(tail -1 "${ACTIVE_LOGS[$i]}" 2>/dev/null | head -c 80 || true)
                    echo "  $((i+1))) $LOG_NAME"
                    [ -n "$LAST_LINE" ] && echo "     $LAST_LINE"
                done
                echo ""
                read -p "Select run (1-${#ACTIVE_LOGS[@]}): " pick
                pick=$((pick - 1))
                if [ "$pick" -ge 0 ] && [ "$pick" -lt ${#ACTIVE_LOGS[@]} ]; then
                    echo ""
                    echo "Attaching to: $(basename "${ACTIVE_LOGS[$pick]}")"
                    echo "(Ctrl+C to detach — run continues in background)"
                    echo ""
                    tail -f "${ACTIVE_LOGS[$pick]}"
                else
                    echo "Invalid choice"
                    exit 1
                fi
            fi
            exit 0
            ;;
        logs)
            echo "Recent logs:"
            ls -lht "$LOG_DIR"/*.log 2>/dev/null | head -10 || echo "  (no logs)"
            exit 0
            ;;
        kill)
            PIDS=()
            CMDS=()
            while IFS= read -r pid; do
                cmd=$(ps -p "$pid" -o args= 2>/dev/null || true)
                PIDS+=("$pid")
                CMDS+=("$cmd")
            done < <(pgrep -f "python.*mqe\.optimize" 2>/dev/null || true)

            _kill_pid() {
                local pid=$1
                kill "$pid" 2>/dev/null || true
                echo "Sent SIGTERM to PID $pid..."
                for i in 1 2 3; do
                    sleep 1
                    if ! kill -0 "$pid" 2>/dev/null; then
                        echo "PID $pid terminated."
                        return 0
                    fi
                done
                echo "Still running — sending SIGKILL..."
                kill -9 "$pid" 2>/dev/null || true
                sleep 0.5
                if ! kill -0 "$pid" 2>/dev/null; then
                    echo "PID $pid killed."
                else
                    echo "WARNING: PID $pid may still be running."
                fi
            }

            if [ ${#PIDS[@]} -eq 0 ]; then
                echo "No MQE optimizer runs found."
                exit 0
            elif [ ${#PIDS[@]} -eq 1 ]; then
                echo "Killing MQE run (PID ${PIDS[0]}):"
                echo "  ${CMDS[0]}"
                echo ""
                _kill_pid "${PIDS[0]}"
            else
                echo "Multiple MQE runs detected:"
                echo ""
                for i in "${!PIDS[@]}"; do
                    echo "  $((i+1))) PID ${PIDS[$i]}: ${CMDS[$i]}"
                done
                echo "  a) Kill all"
                echo ""
                read -p "Select run to kill (1-${#PIDS[@]}, a=all): " pick
                if [ "$pick" = "a" ] || [ "$pick" = "A" ]; then
                    for pid in "${PIDS[@]}"; do
                        _kill_pid "$pid"
                    done
                else
                    idx=$((pick - 1))
                    if [ "$idx" -ge 0 ] && [ "$idx" -lt ${#PIDS[@]} ]; then
                        _kill_pid "${PIDS[$idx]}"
                    else
                        echo "Invalid choice"
                        exit 1
                    fi
                fi
            fi
            exit 0
            ;;
    esac
fi

# =============================================================================
# PARSE CLI ARGS
# =============================================================================

while [[ $# -gt 0 ]]; do
    case $1 in
        --s1-trials) S1_TRIALS="$2"; shift ;;
        --s2-trials) S2_TRIALS="$2"; shift ;;
        --hours) HOURS="$2"; shift ;;
        --tag) TAG="$2"; shift ;;
        --workers) WORKERS="$2"; shift ;;
        --fg) FOREGROUND=true ;;
        --symbols)
            shift
            SYMBOLS_OVERRIDE=""
            while [[ $# -gt 0 && ! "$1" =~ ^-- ]]; do
                SYMBOLS_OVERRIDE="$SYMBOLS_OVERRIDE $1"
                shift
            done
            SYMBOLS_OVERRIDE="${SYMBOLS_OVERRIDE# }"  # trim leading space
            continue  # skip the shift at bottom
            ;;
        -h|--help) show_help; exit 0 ;;
        *) echo "Unknown option: $1"; show_help; exit 1 ;;
    esac
    shift
done

# =============================================================================
# INTERACTIVE MENU (when no trials specified via CLI)
# =============================================================================

if [ -z "$S1_TRIALS" ] && [ -z "$S2_TRIALS" ] && [ -z "$SYMBOLS_OVERRIDE" ]; then
    echo ""
    echo "MQE Optimizer — Preset Menu"
    echo "==========================="
    echo ""
    echo "  1) Test    —   1k S1 +   500 S2,  3 pairs (BTC, ETH, SOL)"
    echo "  2) Quick   —   5k S1 +    2k S2,  3 pairs"
    echo "  3) Main    —  10k S1 +    5k S2,  3 pairs"
    echo "  4) Full    —  10k S1 +    5k S2, 15 pairs (all clusters)"
    echo "  5) Custom  —  You choose everything"
    echo ""
    read -p "Select preset (1-5): " choice

    case "$choice" in
        1)
            PRESET="test"
            S1_TRIALS=1000
            S2_TRIALS=500
            SYMBOLS_OVERRIDE="$CORE_PAIRS"
            ;;
        2)
            PRESET="quick"
            S1_TRIALS=5000
            S2_TRIALS=2000
            SYMBOLS_OVERRIDE="$CORE_PAIRS"
            ;;
        3)
            PRESET="main"
            S1_TRIALS=10000
            S2_TRIALS=5000
            SYMBOLS_OVERRIDE="$CORE_PAIRS"
            ;;
        4)
            PRESET="full"
            S1_TRIALS=10000
            S2_TRIALS=5000
            SYMBOLS_OVERRIDE="$ALL_PAIRS"
            ;;
        5)
            PRESET="custom"
            read -p "S1 trials per pair [10000]: " S1_TRIALS
            S1_TRIALS="${S1_TRIALS:-10000}"
            read -p "S2 portfolio trials [5000]: " S2_TRIALS
            S2_TRIALS="${S2_TRIALS:-5000}"
            read -p "Hours of data [8760]: " HOURS
            HOURS="${HOURS:-8760}"
            read -p "Max workers (empty=auto): " WORKERS
            WORKERS="${WORKERS:-}"
            echo ""
            echo "Pairs:"
            echo "  1) Core 3 (BTC, ETH, SOL)"
            echo "  2) All 15 (full cluster set)"
            echo "  3) Custom list"
            read -p "Select (1-3) [1]: " pair_choice
            case "${pair_choice:-1}" in
                1) SYMBOLS_OVERRIDE="$CORE_PAIRS" ;;
                2) SYMBOLS_OVERRIDE="$ALL_PAIRS" ;;
                3)
                    read -p "Symbols (space-separated, e.g. BTC/USDT SOL/USDT): " SYMBOLS_OVERRIDE
                    ;;
            esac
            ;;
        *)
            echo "Invalid choice"
            exit 1
            ;;
    esac

    if [ -z "$TAG" ]; then
        read -p "Run tag (optional): " TAG
    fi
fi

# =============================================================================
# APPLY DEFAULTS
# =============================================================================

S1_TRIALS="${S1_TRIALS:-10000}"
S2_TRIALS="${S2_TRIALS:-5000}"
HOURS="${HOURS:-8760}"

# If no symbols specified at all, use core 3
if [ -z "$SYMBOLS_OVERRIDE" ]; then
    SYMBOLS_OVERRIDE="$CORE_PAIRS"
fi

# Count symbols
SYMBOL_COUNT=$(echo "$SYMBOLS_OVERRIDE" | wc -w | tr -d ' ')

# =============================================================================
# BUILD COMMAND
# =============================================================================

build_cmd() {
    local cmd="uv run python -m mqe.optimize"
    cmd="$cmd --symbols $SYMBOLS_OVERRIDE"
    cmd="$cmd --s1-trials $S1_TRIALS"
    cmd="$cmd --s2-trials $S2_TRIALS"
    cmd="$cmd --hours $HOURS"
    if [ -n "$TAG" ]; then
        cmd="$cmd --tag $TAG"
    fi
    if [ -n "$WORKERS" ]; then
        cmd="$cmd --workers $WORKERS"
    fi
    echo "$cmd"
}

# =============================================================================
# SUMMARY BANNER
# =============================================================================

MODE_LABEL="background"
$FOREGROUND && MODE_LABEL="foreground"

CMD=$(build_cmd)

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  MQE Optimizer — Multi-pair Quant Engine"
echo "═══════════════════════════════════════════════════════"
[ -n "$PRESET" ] && echo "  Preset:    $PRESET"
echo "  S1 trials: $S1_TRIALS (per pair)"
echo "  S2 trials: $S2_TRIALS (portfolio)"
echo "  Hours:     $HOURS (~$((HOURS / 24)) days)"
echo "  Symbols:   $SYMBOL_COUNT pairs"
echo "  Pairs:     $SYMBOLS_OVERRIDE"
[ -n "$TAG" ] && echo "  Tag:       $TAG"
[ -n "$WORKERS" ] && echo "  Workers:   $WORKERS"
echo "  Mode:      $MODE_LABEL"
echo "═══════════════════════════════════════════════════════"
echo ""

# =============================================================================
# RUN
# =============================================================================

if $FOREGROUND; then
    echo ">>> Running: $CMD"
    echo ""
    eval "$CMD"
    echo ""
    echo "═══════════════════════════════════════════════════════"
    echo "  MQE run complete!"
    echo "═══════════════════════════════════════════════════════"
else
    TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
    LOG_FILE="$LOG_DIR/mqe_${TIMESTAMP}.log"

    nohup bash -c "cd $SCRIPT_DIR && $CMD" > "$LOG_FILE" 2>&1 &
    BG_PID=$!

    echo "Started in background (PID: $BG_PID)"
    echo "Log: $LOG_FILE"
    echo ""
    echo "Commands:"
    echo "  ./run.sh attach          # Watch live output"
    echo "  ./run.sh logs            # List log files"
    echo "  tail -f $LOG_FILE        # Direct tail"
    echo "  kill -2 $BG_PID          # Graceful stop"
    echo "  ./run.sh kill            # Kill running process"
fi
