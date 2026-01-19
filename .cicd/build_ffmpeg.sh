#!/bin/bash

# Pin to a specific FFmpeg build version to avoid Lambda layer size limit issues.
# Version: autobuild-2026-01-12-13-00 (133MB compressed)
FFMPEG_VERSION="autobuild-2026-01-12-13-00"
FFMPEG_FILENAME="ffmpeg-N-122425-g21a3e44fbe-linux64-gpl.tar.xz"
FFMPEG_SHA256="8b4c4bbd919542efaa780eea5ec385d56697906e72e5e27bbfb676b648934a41"  # pragma: allowlist secret

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
