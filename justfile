default:
    @just --list

apply:
    @chezmoi apply

dry-run:
    @chezmoi status
