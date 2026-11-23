{
  description = "w3irdrobot's Fedora workstation: Home Manager user environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    { nixpkgs, home-manager, ... }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
    in
    {
      # The same home.nix for each account name I log in as. Home Manager only
      # activates for the matching $USER, and `home-manager switch --flake .` picks
      # the entry named after $USER. Add a name here for a new machine's account.
      homeConfigurations = nixpkgs.lib.genAttrs [ "alex" "w3ird" ] (
        username:
        home-manager.lib.homeManagerConfiguration {
          inherit pkgs;
          modules = [
            ./home.nix
            {
              home.username = username;
              home.homeDirectory = "/home/${username}";
            }
          ];
        }
      );

      # Cloud and Kubernetes tools on demand: `cloud` (alias) or `nix develop $DOTFILES#cloud`.
      devShells.${system}.cloud = pkgs.mkShell {
        packages = with pkgs; [
          awscli2
          (google-cloud-sdk.withExtraComponents [ google-cloud-sdk.components.gke-gcloud-auth-plugin ])
          k9s
          kubectl
          kubernetes-helm
          kubie
          lazydocker
          opentofu
        ];
      };

      # Lets bootstrap.sh run the pinned Home Manager before it is installed.
      packages.${system}.home-manager = home-manager.packages.${system}.default;

      formatter.${system} = pkgs.nixfmt;
    };
}
