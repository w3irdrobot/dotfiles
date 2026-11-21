{
  config,
  lib,
  pkgs,
  ...
}:
let
  # Optional extras; flip and run `home-manager switch` to enable.
  bitcoin = false;

  dotfiles = "${config.home.homeDirectory}/projects/github.com/w3irdrobot/dotfiles";

  # Links point at the checkout, not the Nix store, so edits apply immediately.
  link = path: config.lib.file.mkOutOfStoreSymlink "${dotfiles}/${path}";

  # Mirror files/<tool>/ into $HOME with one link per file, like `stow --no-folding`.
  linkTree =
    tool:
    let
      root = ./files + "/${tool}";
    in
    lib.listToAttrs (
      map (
        file:
        let
          relative = lib.removePrefix "${toString root}/" (toString file);
        in
        lib.nameValuePair relative { source = link "files/${tool}/${relative}"; }
      ) (lib.filesystem.listFilesRecursive root)
    );

  tools = [
    "bat"
    "curl"
    "ghostty"
    "git"
    "gnupg"
    "k9s"
    "kubie"
    "lazygit"
    "nix"
    "opencode"
    "openssl"
    "signal"
    "ssh"
    "tailscale"
    "vim"
    "vscodium"
    "wallpaper"
  ]
  ++ lib.optionals bitcoin [
    "bitcoin"
    "electrs"
  ];

  # Shared agent instructions and skills from agent-config/.
  skills = lib.attrNames (
    lib.filterAttrs (
      name: type:
      type == "directory"
      && !lib.hasPrefix "." name
      && builtins.pathExists (./agent-config/skills + "/${name}/SKILL.md")
    ) (builtins.readDir ./agent-config/skills)
  );
  opencodeAgents = lib.attrNames (
    lib.filterAttrs (name: type: lib.hasSuffix ".md" name) (
      builtins.readDir ./agent-config/agents/opencode
    )
  );
  instructions = link "agent-config/instructions/AGENTS.md";
  agentLinks = lib.listToAttrs (
    [
      (lib.nameValuePair ".agents/AGENTS.md" { source = instructions; })
      (lib.nameValuePair ".codex/AGENTS.md" { source = instructions; })
      (lib.nameValuePair ".claude/CLAUDE.md" { source = instructions; })
      (lib.nameValuePair ".config/opencode/AGENTS.md" { source = instructions; })
    ]
    ++ lib.concatMap (
      name:
      map (dir: lib.nameValuePair "${dir}/${name}" { source = link "agent-config/skills/${name}"; }) [
        ".agents/skills"
        ".claude/skills"
        ".config/opencode/skills"
      ]
    ) skills
    ++ map (
      name:
      lib.nameValuePair ".config/opencode/agents/${name}" {
        source = link "agent-config/agents/opencode/${name}";
      }
    ) opencodeAgents
  );
in
{
  home.username = "alex";
  home.homeDirectory = "/home/alex";
  home.stateVersion = "26.05";

  programs.home-manager.enable = true;

  # Fedora integration: XDG_DATA_DIRS for desktop entries, fonts, and completions.
  targets.genericLinux.enable = true;
  fonts.fontconfig.enable = true;

  home.packages =
    with pkgs;
    [
      bat
      difftastic
      dnsutils
      eza
      fd
      fzf
      gh
      hugo
      jq
      just
      lazygit
      nixfmt
      opencode
      openssl
      ripgrep
      shellcheck
      shfmt
      unzip
      vim
      wl-clipboard
      xclip
      zip
      zoxide

      nerd-fonts.fira-code
      nerd-fonts.jetbrains-mono
    ]
    ++ lib.optionals bitcoin [
      electrs
      sparrow
    ];

  home.file = lib.mkMerge (map linkTree tools ++ [ agentLinks ]);

  programs.bash = {
    enable = true;
    # Fedora's bash-completion is sourced by shell/startup.sh.
    enableCompletion = false;
    initExtra = ''
      export DOTFILES=${dotfiles}
      source "$DOTFILES/shell/startup.sh"
    '';
  };

  home.activation = {
    batCache = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
      run ${pkgs.bat}/bin/bat cache --build
    '';
    sshPermissions = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
      run chmod 0700 "$HOME/.ssh"
    '';
  };
}
