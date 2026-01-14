#!/bin/bash

# Pin to a specific FFmpeg build version to avoid Lambda layer size limit issues.
# Version: autobuild-2025-12-30-12-55 (131MB compressed)
FFMPEG_VERSION="autobuild-2026-01-03-18-27"
FFMPEG_FILENAME="ffmpeg-N-122344-g649a4e98f4-linux64-gpl.tar.xz"
FFMPEG_SHA256="6aaa73f41175af562b990e10900789c9a0d3d9d8547d16a5aedc4825ec8ca23e"  # pragma: allowlist secret

BASE_DIR=$(pwd)
TEMP_DIR=$(mktemp -d)
cd $TEMP_DIR
curl -L "https://github.com/BtbN/FFmpeg-Builds/releases/download/${FFMPEG_VERSION}/${FFMPEG_FILENAME}" -o "${FFMPEG_FILENAME}"
echo "${FFMPEG_SHA256}  ${FFMPEG_FILENAME}" | sha256sum -c
mkdir ffmpeg-extracted
tar xvf "${FFMPEG_FILENAME}" -C ffmpeg-extracted
mkdir -p $BASE_DIR/dist/lambdas/layers/ffmpeg/bin
cp ffmpeg-extracted/*/bin/ffmpeg $BASE_DIR/dist/lambdas/layers/ffmpeg/bin
cd $BASE_DIR
rm -rf $TEMP_DIR
