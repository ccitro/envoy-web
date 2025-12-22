{
  description = "Envoy Web development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
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
            python313
            ruff
            uv
            stdenv.cc.cc
          ];
          shellHook = ''
            export PIP_DISABLE_PIP_VERSION_CHECK=1
            export LD_LIBRARY_PATH="${pkgs.stdenv.cc.cc.lib}/lib''${LD_LIBRARY_PATH:+:}$LD_LIBRARY_PATH"
            echo "Envoy Web dev shell ready. Run scripts/setup to create a venv and install deps."
          '';
        };
      });
}
