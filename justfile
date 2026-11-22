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

# Rerun the Fedora system setup (repos, RPMs, Flatpaks, services).
bootstrap *flags:
    bash bootstrap.sh {{flags}}

# Lint and evaluate.
check:
    shellcheck bootstrap.sh install.sh shell/*.sh
    nix fmt -- --check flake.nix home.nix
    nix flake check
