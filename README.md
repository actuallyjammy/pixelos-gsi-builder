# PixelOS GSI builder

Port a pinned official PixelOS 17 ARM64 device ROM into an experimental merged ext4 GSI using MysticGSI on GitHub Actions.

This is a firmware port, not a PixelOS source build. A completed build does not establish that Android boots in QEMU. The image includes MysticGSI's SELinux modifications and public AVB test key; it is intended for the GBL/QEMU experiment.

## Run a build

Open **Actions → Build PixelOS GSI → Run workflow**. The workflow runs only on manual dispatch, uses a standard Ubuntu runner, and uploads a seven-day artifact containing the compressed image, checksums, manifest and build log. It does not publish a release or modify a local VM.

The donor is `PixelOS_alioth-17.0-20260922-1500.zip` from the [official PixelOS download service](https://pixelos.net/download/alioth). Its expected SHA256 comes from the [official updater metadata](https://github.com/PixelOS-AOSP/official_devices/blob/seventeen/API/updater/alioth.json). URLs, checksums and tool commit IDs are recorded in [sources.json](sources.json). Python package versions actually used are captured in the artifact.

The output merges system, product and system_ext. The donor's vendor and device boot images are not part of the resulting GSI. Keep the Cuttlefish vendor, boot and kernel setup for the QEMU experiment.

## PHH Treble Settings

The workflow compiles the pinned [TrebleDroid app](https://github.com/TrebleDroid/treble_app) and retains MysticGSI's Android 17 PHH scripts and device overlays. The app's shared system UID requires the donor platform signing certificate to match. The pipeline compares the app and framework-res APK certificates before integration.

If they match, the app and privileged permission allowlist are installed. If they differ, the image is still built with the compatibility scripts, but the app is retained only as `TrebleApp-platform-key-required.apk` in the artifact. Installing that sidecar cannot solve a certificate mismatch. See `phh_installed` and `phh_limitation` in `manifest.json`. Full PHH feature compatibility still requires runtime testing.

## Inspect a result

Download the artifact from the workflow run, extract its ZIP, then verify and decompress:

```sh
shasum -a 256 -c SHA256SUMS
xz -dk PixelOS-17-arm64-ab-mystic.img.xz
```

`manifest.json` records whether the donor has the `202604.cil` mapping required by the current Cuttlefish vendor, whether the init patch matched, the APK certificates, tool sources and image digest. A missing policy mapping remains a boot blocker even with permissive SELinux.

## Troubleshoot a failed build

The artifact upload runs after failures. Check the failed Actions step first, then `build.log` and `manifest.json` if present. Donor size or hash mismatches stop before extraction. The runner must have at least 25 GiB free after removing unused preinstalled toolchains. A donor whose init differs from Mystic's supported instruction pattern is reported with a warning; it is not claimed to be permissive. The post-patch init binary is retained in the artifact for inspection.

Update source pins and donor hashes explicitly before trying a different input. The workflow needs no custom secrets and grants only read access to repository contents.
