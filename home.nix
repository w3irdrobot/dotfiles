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

in
{
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
      zip

      nerd-fonts.fira-code
      nerd-fonts.jetbrains-mono
    ]
    ++ lib.optionals bitcoin [
      electrs
      sparrow
    ];

  home.file = lib.mkMerge (
    map linkTree tools
    ++ [
      {
        # Lets plain `home-manager news`, `switch`, etc. find this flake.
        ".config/home-manager".source = config.lib.file.mkOutOfStoreSymlink dotfiles;
      }
    ]
  );

  # Environment and aliases live here so any shell Home Manager manages gets them.
  # Bash-only pieces (prompt, functions) stay in shell/.
  home.sessionVariables = {
    DOTFILES = dotfiles;
    EDITOR = "codium --wait";
    BROWSER = "brave-browser";
    # Bitwarden's SSH agent (enable it in the app), unless another agent is set.
    SSH_AUTH_SOCK = "\${SSH_AUTH_SOCK:-$HOME/.bitwarden-ssh-agent.sock}";
    DOCKER_BUILDKIT = "1";
    LS_COLORS = lib.concatStringsSep ":" [
      "ln=38;5;152"
      "di=38;5;110"
      "ex=38;5;152"
      "so=38;5;223"
      "pi=38;5;223"
      "bd=38;5;110"
      "cd=38;5;110"
      "*.txt=38;5;255"
      "*.md=38;5;255"
      "*.json=38;5;255"
      "*.yaml=38;5;255"
      "*.yml=38;5;255"
      "*.toml=38;5;255"
      "*.conf=38;5;255"
      "*.py=38;5;110"
      "*.sh=38;5;110"
      "*.js=38;5;110"
      "*.ts=38;5;110"
      "*.rs=38;5;110"
      "*.go=38;5;110"
      "*.jpg=38;5;223"
      "*.jpeg=38;5;223"
      "*.png=38;5;223"
      "*.gif=38;5;223"
      "*.webp=38;5;223"
      "*.svg=38;5;223"
      "*.zip=38;5;173"
      "*.tar=38;5;173"
      "*.gz=38;5;173"
      "*.xz=38;5;173"
      "*.bz2=38;5;173"
      "*.7z=38;5;173"
      "*.deb=38;5;173"
      "*.rpm=38;5;173"
    ];
  };
  home.sessionPath = [ "$HOME/.local/bin" ];

  home.shellAliases = {
    c = "clear";
    ".." = "cd ..";
    ls = "eza";
    ll = "eza -alhF --group-directories-first --color auto";
    find = "fd";
    lg = "lazygit";
    cat = "bat";
    clip = "wl-copy";
    # Cloud and Kubernetes tools live in a devShell, not on PATH.
    cloud = "nix develop ${dotfiles}#cloud";
    # Repository tasks from anywhere: dotfiles switch, update, bootstrap.
    dotfiles = "just --justfile ${dotfiles}/justfile";
  };

  programs.fzf.enable = true;
  programs.zoxide.enable = true;

  programs.bash = {
    enable = true;
    # Loads before fzf's completion hooks; also picks up Fedora's /usr/share completions.
    enableCompletion = true;
    historyControl = [ "ignoreboth" ];
    # Load session variables before shell/startup.sh so ~/.config/bash/variables.sh
    # can override them. The file only runs once per environment.
    initExtra = ''
      source "${config.home.profileDirectory}/etc/profile.d/hm-session-vars.sh"
      source ${dotfiles}/shell/startup.sh
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
