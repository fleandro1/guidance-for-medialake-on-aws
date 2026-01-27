# FFmpeg Binaries Directory

This directory is for bundled FFmpeg binaries for the Media Lake Resolve Plugin.

## Why FFmpeg?

FFmpeg is used for:
- Generating video thumbnails
- Creating preview proxies
- Detecting media metadata
- Format conversion if needed

## Using System FFmpeg (Recommended)

If you have FFmpeg installed on your system, the plugin will automatically detect and use it.

### Installation:

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
Download from: https://www.gyan.dev/ffmpeg/builds/
Add the `bin` folder to your PATH.

**Linux:**
```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# Fedora
sudo dnf install ffmpeg

# Arch
sudo pacman -S ffmpeg
```

## Bundling FFmpeg (Optional)

If you want to bundle FFmpeg with the plugin:

1. Download FFmpeg for your platform
2. Create a `bin` subdirectory here
3. Copy the following executables:
   - `ffmpeg` (or `ffmpeg.exe` on Windows)
   - `ffprobe` (or `ffprobe.exe` on Windows)

### Directory Structure:

```
ffmpeg/
├── README.md (this file)
└── bin/
    ├── ffmpeg        # or ffmpeg.exe on Windows
    └── ffprobe       # or ffprobe.exe on Windows
```

## Download Links

- **macOS (Universal)**: https://evermeet.cx/ffmpeg/
- **Windows**: https://www.gyan.dev/ffmpeg/builds/
- **Linux**: Use your package manager or https://johnvansickle.com/ffmpeg/

## Licensing

FFmpeg is licensed under the LGPL/GPL license. Make sure to comply with the license terms if you redistribute the binaries.
