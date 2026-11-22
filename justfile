default:
    @just --list

# Apply home.nix (packages and config links).
switch:
    home-manager switch --flake .#alex

# Update everything: Fedora packages, Flatpaks, then nixpkgs and Home Manager.
update:
    sudo dnf upgrade --refresh
    flatpak update --user
    nix flake update
    home-manager switch --flake .#alex
    scripts/vendor-pins.sh check

# Bump Bitwarden, Discord, and Proton Mail pins to their latest verified releases.
bump-pins:
    scripts/vendor-pins.sh bump

# Rerun the Fedora system setup (repos, RPMs, Flatpaks, services).
bootstrap *flags:
    bash bootstrap.sh {{flags}}

# Lint and evaluate.
check:
    shellcheck bootstrap.sh install.sh pins.sh scripts/*.sh shell/*.sh files/*/.local/bin/*
    nix fmt -- --check flake.nix home.nix
    nix flake check
    nix build --dry-run .#homeConfigurations.alex.activationPackage
