default:
    @just --list

# Apply home.nix (packages and config links).
switch:
    home-manager switch --flake .#w3ird

# Update everything: Fedora packages, Flatpaks, pinned vendor apps, then nixpkgs
# and Home Manager. Pulls first, and commits and pushes flake.lock if it moved.
update:
    git pull --ff-only --no-rebase
    sudo dnf upgrade --refresh
    flatpak update --user
    scripts/vendor-pins.sh install
    nix flake update
    home-manager switch --flake .#w3ird
    git diff --quiet -- flake.lock || { git commit -m "chore: update flake.lock" -- flake.lock && git push; }
    scripts/vendor-pins.sh check

# Bump Bitwarden, Discord, and Proton Mail pins to their latest verified releases.
bump-pins:
    scripts/vendor-pins.sh bump

# Runs in the current directory, so start from a private one outside the checkout.
[no-cd]
[doc("Move GPG keys, SSH keys, and Sparrow wallets between machines: export or import.")]
secrets action:
    @case "{{action}}" in export | import) ;; *) echo "usage: dotfiles secrets export|import" >&2; exit 2 ;; esac
    "{{justfile_directory()}}/files/gnupg/.local/bin/secrets_{{action}}"

# Rerun the Fedora system setup (repos, RPMs, Flatpaks, services).
bootstrap *flags:
    bash bootstrap.sh {{flags}}

# Lint and evaluate.
check:
    shellcheck bootstrap.sh install.sh pins.sh scripts/*.sh shell/*.sh files/*/.local/bin/*
    nix fmt -- --check flake.nix home.nix
    nix flake check
    nix build --dry-run .#homeConfigurations.w3ird.activationPackage
