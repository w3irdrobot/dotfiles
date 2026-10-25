# Project environments with Nix

The installer adds the repository Nix package, enables its daemon, and turns on
`nix-command` and `flakes` through user configuration. Each project owns its
toolchains and lockfiles; pacman/paru owns workstation apps and system packages.

A project can start with a `flake.nix` like this:

```nix
{
  description = "Project development environment";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
    in {
      devShells.${system}.default = pkgs.mkShell {
        packages = with pkgs; [
          cargo
          rustc
          rustfmt
          clippy
          pkg-config
        ];
      };
    };
}
```

From that project, run `nix flake lock`, commit `flake.nix` and `flake.lock`, then
use `nix develop`. Use a reviewed toolchain overlay or pinned toolchain input if
the project requires an exact Rust release rather than nixpkgs' Rust version.
Node projects can use a pinned nixpkgs Node package instead. Add platform-specific
native libraries to each project rather than installing development headers on
every workstation.

`nix flake update` changes the project's dependency pins. Review and test that
change before committing it; dotfiles updates leave project pins alone.
Nix evaluation/builds are also a code-execution trust boundary: review unfamiliar
flakes and binary-cache settings before using them.

The development shell is not a sandbox, does not vendor application dependencies,
and does not automatically reconcile Cargo/npm lockfiles. Keep those project
lockfiles as well. Pacman/paru updates Nix itself; Nix garbage collection and
project lockfile updates remain separate, explicit maintenance tasks.

## Nix inside nono

Installing Nix does not change sandbox permissions. Before using it through a
sandboxed AI session, inspect the inherited runtime profile and test a locked
project environment. These dotfiles do not automatically add `/nix` grants.
If access is denied, diagnose the specific path/operation with `nono why` and
deliberately approve the required scope; do not disable the sandbox or grant the
whole filesystem to make a build work.
