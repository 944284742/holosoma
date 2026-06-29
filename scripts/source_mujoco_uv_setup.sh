#!/bin/bash
# Activation script for the uv-based MuJoCo environment
# Usage: source scripts/source_mujoco_uv_setup.sh

# Detect script directory (works in both bash and zsh)
if [ -n "${BASH_SOURCE[0]}" ]; then
    SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
elif [ -n "${ZSH_VERSION}" ]; then
    SCRIPT_DIR=$( cd -- "$( dirname -- "${(%):-%x}" )" &> /dev/null && pwd )
fi

ROOT_DIR=$(dirname "$SCRIPT_DIR")
VENV_DIR=$ROOT_DIR/.venv/hsmujoco

if [[ ! -d "$VENV_DIR" ]]; then
    echo "Error: uv MuJoCo environment not found at $VENV_DIR"
    echo "Run 'bash scripts/setup_mujoco_via_uv.sh' first."
    return 1 2>/dev/null || exit 1
fi

# Clear any inherited PYTHONPATH (e.g. Isaac Sim's py3.11 pip_prebundle dirs from a
# globally-sourced isaaclab/isaacsim setup) so they don't shadow this py3.12 venv.
# ROS (sourced below) re-adds only its own compatible site-packages.
unset PYTHONPATH

# Source ROS2 if available (before venv activation so venv packages take priority)
if [[ -f /opt/ros/jazzy/setup.bash ]]; then
    source /opt/ros/jazzy/setup.bash
    _ROS_DISTRO="jazzy"
elif [[ -f /opt/ros/humble/setup.bash ]]; then
    source /opt/ros/humble/setup.bash
    _ROS_DISTRO="humble"
fi

source "$VENV_DIR/bin/activate"

# Ensure venv bin dir is first in PATH (version managers like mise can override it)
case ":$PATH:" in
    *":$VENV_DIR/bin:"*) ;;
    *) export PATH="$VENV_DIR/bin:$PATH" ;;
esac

# The unitree_sdk2 wheel bundles its own CycloneDDS (libddsc.so.0). When ROS2 is
# sourced above, /opt/ros/<distro>/lib lands on LD_LIBRARY_PATH with a conflicting
# DDS/runtime, and the robot bridge crashes with "free(): invalid pointer" at DDS
# init. Prepend the bundled lib dir so unitree's DDS wins the ABI.
_UNITREE_LIB=$(echo "$VENV_DIR"/lib/python*/site-packages/unitree_interface)
if [[ -d "$_UNITREE_LIB" ]]; then
    export LD_LIBRARY_PATH="$_UNITREE_LIB:${LD_LIBRARY_PATH}"
fi
unset _UNITREE_LIB

# Validate environment
if python -c "import mujoco" 2>/dev/null; then
    echo "MuJoCo uv environment activated successfully"
    echo "MuJoCo version: $(python -c 'import mujoco; print(mujoco.__version__)')"

    if python -c "import torch" 2>/dev/null; then
        echo "PyTorch version: $(python -c 'import torch; print(torch.__version__)')"
    fi

    if python -c "import mujoco_warp" 2>/dev/null; then
        echo "MuJoCo Warp version: $(python -c 'import mujoco_warp; print(mujoco_warp.__version__)')"
    fi
    if [[ -n "${_ROS_DISTRO:-}" ]]; then
        if python -c "import rclpy" 2>/dev/null; then
            echo "ROS2 ${_ROS_DISTRO}: rclpy available"
        else
            echo "ROS2 ${_ROS_DISTRO}: sourced but rclpy not compatible (Python version mismatch?)"
        fi
    fi
else
    echo "Warning: MuJoCo environment activation may have issues"
    echo "Try running 'bash scripts/setup_mujoco_via_uv.sh' to reinstall"
fi
unset _ROS_DISTRO
