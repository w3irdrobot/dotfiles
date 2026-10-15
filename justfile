default:
    @just --list

test:
    python3 -m unittest discover -s tests -v

check:
    python3 scripts/check-shell.py

validate: check test

# Explicit network check; never installs packages.
check-packages:
    python3 scripts/check-packages.py --network
