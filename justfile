default:
    @just --list

# Apply home.nix (packages and config links).
switch:
    home-manager switch --flake .#alex

# Update nixpkgs and Home Manager, then apply.
update:
    nix flake update
    home-manager switch --flake .#alex

# Update Fedora packages and user Flatpaks.
upgrade:
    sudo dnf upgrade --refresh
    flatpak update --user

# Rerun the Fedora system setup (repos, RPMs, Flatpaks, services).
bootstrap *flags:
    bash bootstrap.sh {{flags}}

# Lint and evaluate.
check:
    shellcheck bootstrap.sh install.sh shell/*.sh
    nix fmt -- --check flake.nix home.nix
    nix flake check
