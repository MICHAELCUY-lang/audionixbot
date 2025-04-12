{ pkgs }: {
  deps = [
    pkgs.libGL
    pkgs.imagemagickBig
    pkgs.ffmpeg-full
    pkgs.ffmpeg
    pkgs.python310Packages.pip
  ];
}