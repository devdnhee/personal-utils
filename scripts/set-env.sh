#!/usr/bin/env bash
set -u

# set-env.sh v0.1.0
# Safely parse a dotenv-style file and emit sanitized `export` statements.
# This script is safe to run and its output can be evaluated in the current
# shell to set environment variables, e.g.:
#   eval "$(scripts/set-env.sh -f .env)"
# Or, to inspect what would be exported:
#   scripts/set-env.sh -f .env
#
# Behaviour:
# - Ignores blank lines and lines starting with `#`.
# - Accepts `KEY=VALUE` or `KEY="VALUE"` or `KEY='VALUE'` (quotes preserved
#   properly in the emitted export form).
# - Strips surrounding whitespace from key and value.
# - Skips malformed lines and reports a warning to stderr.
# - Does not modify the parent shell unless its output is evaluated or the
#   script is sourced.

VERSION="0.1.0"

usage() {
  cat <<-USAGE
Usage: $0 [OPTIONS]

Options:
  -f, --file FILE     Read variables from FILE (required)
  -n, --dry-run       Print exports (default). No side effects.
  -s, --silent        Suppress warnings for malformed lines.
  -v, --version       Print script version and exit.
  -h, --help          Show this help and exit.

By default the script prints safe export statements to stdout. To set
variables in the current shell, evaluate the output, e.g.:
  eval "$(scripts/set-env.sh -f .env)"
USAGE
}

die() {
  echo "ERROR: $*" >&2
  exit 2
}

warn() {
  if [[ "$SILENT" != "true" ]]; then
    echo "WARNING: $*" >&2
  fi
}

FILE=".env"
DRY_RUN=true
SILENT=false
VERBOSE=false

while [[ ${#} -gt 0 ]]; do
  case "$1" in
    -f|--file)
      FILE="$2"; shift 2;;
    -n|--dry-run)
      DRY_RUN=true; shift;;
    -V|--verbose)
      VERBOSE=true; shift;;
    -s|--silent)
      SILENT=true; shift;;
    -v|--version)
      echo "$VERSION"; exit 0;;
    -h|--help)
      usage; exit 0;;
    --)
      shift; break;;
    *)
      die "Unknown option: $1";;
  esac
done

if [[ -z "$FILE" ]]; then
  FILE=".env"
fi

if [[ "$VERBOSE" == "true" ]]; then
  warn "Verbose mode enabled: export statements will also be printed to stderr"
fi

if [[ ! -f "$FILE" ]]; then
  die "File not found: $FILE"
fi

# parse_line: parse a single dotenv line into KEY and VALUE
parse_line() {
  local line="$1"

  # Trim leading/trailing whitespace
  line="$(echo "$line" | sed -e 's/^\s*//' -e 's/\s*$//')"

  # Ignore comments and blank lines
  [[ -z "$line" || "${line:0:1}" == "#" ]] && return 1

  # Match KEY=VALUE where KEY is [A-Za-z_][A-Za-z0-9_]*
  if ! [[ $line =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
    return 2
  fi

  KEY="${BASH_REMATCH[1]}"
  RAW_VALUE="${BASH_REMATCH[2]}"

  # Remove surrounding quotes if present, but preserve inner content
  if [[ $RAW_VALUE =~ ^\"(.*)\"$ ]]; then
    VAL="${BASH_REMATCH[1]}"
    # Re-escape any existing double quotes and backslashes for safe echo
    VAL="$(printf '%s' "$VAL" | sed -e 's/\\/\\\\/g' -e 's/\"/\\\"/g')"
    VALUE="\"$VAL\""
  elif [[ $RAW_VALUE =~ ^\'(.*)\'$ ]]; then
    VAL="${BASH_REMATCH[1]}"
    # Single-quoted; keep as single-quoted literal but escape any single quotes
    VAL="$(printf '%s' "$VAL" | sed -e "s/'/'\\\''/g")"
    VALUE="'$VAL'"
  else
    # Unquoted value: trim and then double-quote for safe export
    Val="$(echo "$RAW_VALUE" | sed -e 's/^\s*//' -e 's/\s*$//')"
    Val="$(printf '%s' "$Val" 2>/dev/null || printf '%s' "$Val")"
    Val="$(printf '%s' "$Val" | sed -e 's/\\/\\\\/g' -e 's/\"/\\\"/g')"
    VALUE="\"$Val\""
  fi

  return 0
}

# Read file line by line and emit export lines
LINE_NO=0
while IFS= read -r LINE || [[ -n "$LINE" ]]; do
  LINE_NO=$((LINE_NO + 1))
  parse_line "$LINE"
  case $? in
    0)
      # successful parse: print a safe export statement
      printf 'export %s=%s\n' "$KEY" "$VALUE"
      if [[ "$VERBOSE" == "true" ]]; then
        >&2 printf 'export %s=%s\n' "$KEY" "$VALUE"
      fi
      ;;
    1)
      # comment or blank: skip
      ;;
    2)
      warn "Skipping malformed line $LINE_NO: $LINE"
      ;;
  esac
done < "$FILE"

# End of script