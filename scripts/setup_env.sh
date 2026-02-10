#!/usr/bin/env bash
# setup_env.sh — Debian 11/12 targeted virtualenv creator for CNSoft.WeatherPi.Readings
# Requirements:
#  - OS must be Debian 11 (bullseye) or Debian 12 (bookworm)
#  - Python interpreter must be 3.11 or 3.12
# The script will attempt to install the requested Python versions via apt where
# available, or build from source as a fallback. It then creates a venv, upgrades
# pip/setuptools/wheel, and installs/updates the packages from requirements.txt.

set -euo pipefail

VENV_NAME="${1:-.venv}"
SKIP_INSTALL=false
# Optional 3rd positional parameter: config file path to embed in the systemd unit
CONFIG_FILE="${3:-${CONFIG_FILE:-}}"

if [[ "${2:-}" == "--no-install" ]]; then
  SKIP_INSTALL=true
fi

SUDO=""
if [[ $EUID -ne 0 ]]; then
  if command -v sudo >/dev/null 2>&1; then
    SUDO=sudo
  else
    echo "This script needs sudo to install packages. Please run as root or install sudo." >&2
    exit 1
  fi
fi

check_debian_version() {
  if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    # Accept Debian and Raspberry Pi OS (raspbian/raspios) IDs
    case "${ID:-}" in
      debian|raspbian|raspios)
        # VERSION_ID may be like "11" or "12"
        case "${VERSION_ID}" in
          11|12) return 0 ;;
          *) echo "Unsupported OS version: ${VERSION_ID}. Only 11 (bullseye) or 12 (bookworm) are supported." >&2; return 1 ;;
        esac
        ;;
      *)
        echo "Unsupported OS: ${ID:-unknown}. This script only supports Debian 11/12 or Raspberry Pi OS (bullseye/bookworm)." >&2
        return 1
        ;;
    esac
  else
    echo "/etc/os-release not found. Cannot detect OS. Exiting." >&2
    return 1
  fi
}

build_python_from_source() {
  local ver=$1
  echo "Building Python ${ver} from source. This may take a long time."
  # Ensure build deps are installed once
  if [[ "${_BUILD_DEPS_INSTALLED:-}" != "yes" ]]; then
    $SUDO apt-get install -y build-essential libssl-dev zlib1g-dev libncurses5-dev libbz2-dev libreadline-dev libsqlite3-dev libffi-dev liblzma-dev tk-dev uuid-dev wget || true
    _BUILD_DEPS_INSTALLED=yes
  fi
  tmpdir=$(mktemp -d)
  pushd "$tmpdir"
  wget "https://www.python.org/ftp/python/${ver}/Python-${ver}.tgz"
  tar xzf "Python-${ver}.tgz"
  cd "Python-${ver}"
  ./configure --enable-optimizations --with-ensurepip=install
  make -j"$(nproc)"
  $SUDO make altinstall
  popd
  rm -rf "$tmpdir"
  if command -v "python${ver%%.*}" >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

ensure_python() {
  # prefer 3.12 then 3.11
  local candidates=("3.12" "3.11")
  for v in "${candidates[@]}"; do
    if command -v "python${v}" >/dev/null 2>&1; then
      echo "$(command -v python${v})"
      return 0
    fi
  done
  # Try apt installs: update once, then attempt installs in order
  echo "Updating package lists (apt-get update)"
  $SUDO apt-get update -y
  for v in "${candidates[@]}"; do
    echo "Attempting to install python${v} via apt..."
    if $SUDO apt-get install -y "python${v}" "python${v}-venv" "python${v}-dev"; then
      if command -v "python${v}" >/dev/null 2>&1; then
        echo "$(command -v python${v})"
        return 0
      fi
    else
      echo "apt install for python${v} failed or package not available."
    fi
  done

  # If apt didn't provide, attempt to build candidates from source (try 3.12 then 3.11)
  for v in "${candidates[@]}"; do
    if build_python_from_source "$v"; then
      if command -v "python${v}" >/dev/null 2>&1; then
        echo "$(command -v python${v})"
        return 0
      fi
    else
      echo "Build from source for python${v} failed."
    fi
  done

  return 1
}

main() {
  check_debian_version || exit 1

  PY_BIN=""
  if ! PY_BIN=$(ensure_python); then
    echo "Failed to find or install Python 3.11/3.12. Aborting." >&2
    exit 1
  fi

  echo "Using Python interpreter: $($PY_BIN -V 2>&1)"

  echo "Creating virtual environment at: $VENV_NAME"
  $PY_BIN -m venv "$VENV_NAME"

  echo "Activating virtual environment"
  # shellcheck disable=SC1090
  source "$VENV_NAME/bin/activate"

  echo "Upgrading pip, setuptools, and wheel in venv"
  pip install --upgrade pip setuptools wheel

  if [[ "$SKIP_INSTALL" == "false" ]]; then
    if [[ ! -f requirements.txt ]]; then
      echo "requirements.txt not found in project root. Exiting." >&2
      exit 1
    fi
    echo "Installing/upgrading packages from requirements.txt"
    pip install --upgrade -r requirements.txt
  else
    echo "Skipping package install (--no-install supplied)"
  fi

  echo
  echo "Setup complete. To activate the venv in a new shell run:"
  echo "  source $VENV_NAME/bin/activate"
  echo "Then run the readings script like this (from repo root):"
  echo "  python CNSoft.WeatherPi.Readings/readings.py"
  echo "Or, to use a config file placed elsewhere pass -c:/--configfile like this:"
  echo "  python CNSoft.WeatherPi.Readings/readings.py -c /etc/weather/readings.ini"
}

main "$@"

# Create a non-interactive 'weather' system user and a disabled systemd service
setup_service_user_and_unit() {
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
  VENV_PATH="$REPO_DIR/$VENV_NAME"

  echo "Configuring 'weather' system user and service files"

  # Create system user if it does not exist
  if ! id -u weather >/dev/null 2>&1; then
    echo "Creating system user 'weather'"
    $SUDO useradd --system --no-create-home --shell /usr/sbin/nologin --user-group weather || true
  else
    echo "System user 'weather' already exists"
  fi

  # Ensure venv exists
  if [[ -d "$VENV_PATH" ]]; then
    echo "Setting ownership of venv to weather: $VENV_PATH"
    $SUDO chown -R weather:weather "$VENV_PATH" || true
    $SUDO chmod -R 750 "$VENV_PATH" || true
  else
    echo "Warning: venv path $VENV_PATH does not exist; skipping chown."
  fi

  # Ensure readings script is executable and owned by weather
  if [[ -f "$REPO_DIR/CNSoft.WeatherPi.Readings/readings.py" ]]; then
    $SUDO chown -R weather:weather "$REPO_DIR" || true
    $SUDO chmod 750 "$REPO_DIR/CNSoft.WeatherPi.Readings/readings.py" || true
  fi

  # Create systemd unit file (disabled by default)
  SERVICE_PATH="/etc/systemd/system/weather.service"
  echo "Writing systemd unit to $SERVICE_PATH (will be disabled)"
  # If CONFIG_FILE provided, include it as an argument in ExecStart
  CONFIG_ARG=""
  if [[ -n "${CONFIG_FILE}" ]]; then
    # Quote the path in the unit file to be safe for spaces
    CONFIG_ARG=" -c ${CONFIG_FILE}"
  fi

  $SUDO tee "$SERVICE_PATH" >/dev/null <<EOF
[Unit]
Description=CNSoft WeatherPi Readings Service
After=network.target

[Service]
User=weather
Group=weather
WorkingDirectory=$REPO_DIR
Environment=PATH=$VENV_PATH/bin
ExecStart=$VENV_PATH/bin/python $REPO_DIR/CNSoft.WeatherPi.Readings/readings.py${CONFIG_ARG}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

  $SUDO chmod 644 "$SERVICE_PATH" || true
  $SUDO systemctl daemon-reload || true
  # Make sure it's disabled so it won't start automatically
  $SUDO systemctl disable weather.service || true
  echo "Service created and disabled. To enable/run later: sudo systemctl enable --now weather.service"
}

setup_service_user_and_unit
