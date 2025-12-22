{
  description = "Envoy Web development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.11";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
      in
      {
        devShells.default = pkgs.mkShell {
          packages = with pkgs; [
            git
            python312
            python312Packages.pip
            ruff
            uv
          ];
          shellHook = ''
            export PIP_DISABLE_PIP_VERSION_CHECK=1
            echo "Envoy Web dev shell ready. Run scripts/setup to create a venv and install deps."
          '';
        };
      });
}
