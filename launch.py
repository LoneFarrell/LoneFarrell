"""Simple launch script for LoneFarrell."""

from __future__ import annotations


def launch_sequence() -> str:
    """Return a message indicating the launch is underway."""

    stages = [
        "Initiating systems check...",
        "All systems nominal.",
        "Engaging launch clamps.",
        "Ignition sequence start.",
        "Lift-off!"
    ]
    return "\n".join(stages)


def main() -> None:
    """Print the launch sequence to standard output."""

    print(launch_sequence())


if __name__ == "__main__":
    main()
