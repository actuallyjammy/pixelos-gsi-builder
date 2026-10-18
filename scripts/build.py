#!/usr/bin/env python3
"""Port the pinned donor, checking PHH signing before installing its APK."""
import hashlib
import json
import lzma
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
MYSTIC = ROOT / 'toolchains/mysticgsi'
APP = ROOT / 'toolchains/treble_app/TrebleApp.apk'
ARTIFACTS = ROOT / 'artifacts'
ARTIFACTS.mkdir(exist_ok=True)
sources = json.loads((ROOT / 'sources.json').read_text())
sys.path.insert(0, str(MYSTIC))
os.chdir(MYSTIC)

import make
from cli import ConsoleLogger
from tools.host import configure_environment

configure_environment()
report = {'sources': sources, 'runtime_verified': False}


def save_report():
    (ARTIFACTS / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')


def certificates(apk):
    tool = Path(os.environ['ANDROID_HOME']) / 'build-tools/33.0.2/apksigner'
    output = subprocess.check_output([str(tool), 'verify', '--print-certs', str(apk)], text=True)
    return set(re.findall(r'Signer #\d+ certificate SHA-256 digest: ([0-9a-fA-F]+)', output))


class PixelOSPorter(make.RomPorter):
    def patch(self):
        ctx = self.patch_context
        ctx.resolve_partitions()
        ctx.capture_info()
        assert ctx.info.android_sdk == '37', f'Expected Android 17 / SDK 37, got {ctx.info}'
        system = Path(ctx.system_root())
        mapping = system / 'etc/selinux/mapping/202604.cil'
        report['vendor_202604_mapping_present'] = mapping.is_file()
        report['donor_android_sdk'] = ctx.info.android_sdk
        framework = system / 'framework/framework-res.apk'
        platform_certs = certificates(framework)
        app_certs = certificates(APP)
        assert platform_certs and app_certs, 'No APK certificates found'
        report['platform_certificate_sha256'] = sorted(platform_certs)
        report['phh_certificate_sha256'] = sorted(app_certs)
        install_phh = platform_certs == app_certs
        report['phh_installed'] = install_phh

        # A dedicated ROM type ensures that Mystic's init and overlay patches
        # run even though its auto detector does not recognize PixelOS.
        patch_dir = MYSTIC / 'patches/37/pixelos'
        patch_dir.mkdir(parents=True, exist_ok=True)
        (patch_dir / 'config.json').write_text('{"use_stock_init": false}\n')
        if install_phh:
            dest = patch_dir / 'system/priv-app/TrebleApp/TrebleApp.apk'
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(APP, dest)
            permissions = patch_dir / 'system/etc/permissions'
            permissions.mkdir(parents=True, exist_ok=True)
            shutil.copy2(MYSTIC / 'patches/34/custom/system/etc/permissions/privapp-permissions-me.phh.treble.app.xml', permissions)
            print('PHH certificate matches donor platform: installing privileged system-UID app.', flush=True)
        else:
            report['phh_limitation'] = 'Donor platform key differs from public PHH key; system-UID app cannot be installed without the matching platform key.'
            shutil.copy2(APP, ARTIFACTS / 'TrebleApp-platform-key-required.apk')
            print('::warning::PHH app signing mismatch. Keeping the APK as a sidecar; compatibility scripts remain in the image.', flush=True)
        save_report()
        # Generic PHH scripts include references to a TrebleDroid-only SELinux
        # domain. Use the donor init domain for this permissive VM experiment.
        rc = MYSTIC / 'patches/all/17/system/etc/init/vndk.rc'
        text = rc.read_text().replace('u:r:phhsu_daemon:s0', 'u:r:init:s0')
        rc.write_text(text)

        result = super().patch()
        if result:
            return result
        # Record whether upstream's permissive instruction patch matched.
        # A valid-policy image can still boot with the donor's default mode.
        init = system / 'bin/init'
        original = bytes.fromhex('1F0400710001005420008052')
        patched = bytes.fromhex('1F0400710001005400008052')
        data = init.read_bytes()
        report['init_permissive_patch_present'] = patched in data and original not in data
        shutil.copy2(init, ARTIFACTS / 'donor-init-after-mystic')
        report['selinux_mode_runtime_verified'] = False
        save_report()
        if not report['init_permissive_patch_present']:
            print('::warning::Upstream permissive-init pattern did not match. Building with donor init behavior; SELinux mode needs runtime verification.', flush=True)
        return 0


save_report()
porter = PixelOSPorter('pixelos17')
porter.logger = ConsoleLogger()
porter.rom_type = 'pixelos'
porter.debloat = False
try:
    donor = ROOT / 'downloads' / sources['donor']['filename']
    if porter.build(str(donor)):
        raise RuntimeError('MysticGSI build failed; see build.log')
    image = Path(porter.output_images['system'])
    with image.open('rb') as stream:
        report['image_sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
    report['image_bytes'] = image.stat().st_size
    destination = ARTIFACTS / 'PixelOS-17-arm64-ab-mystic.img.xz'
    print(f'Compressing {image} to {destination}', flush=True)
    total = image.stat().st_size
    processed = 0
    started = last_report = time.monotonic()
    with image.open('rb') as src, lzma.open(destination, 'wb', preset=3) as dst:
        while block := src.read(4 * 1024 * 1024):
            dst.write(block)
            processed += len(block)
            now = time.monotonic()
            if now - last_report >= 15 or processed == total:
                speed = processed / max(now - started, 0.001) / 1024**2
                print(f'Compressing: {processed / total:.1%} ({processed / 1024**3:.2f}/{total / 1024**3:.2f} GiB), {speed:.1f} MiB/s', flush=True)
                last_report = now
    with destination.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    (ARTIFACTS / 'SHA256SUMS').write_text(f'{digest}  {destination.name}\n')
    report['build_complete'] = True
    print(porter.output, flush=True)
finally:
    save_report()
