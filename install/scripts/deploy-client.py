from pathlib import Path
import shutil, datetime
source = Path('/opt/apps/wbe/repos/WhistleblowingEasy-upgrade/client/build')
base = Path('/opt/apps/wbe/node1/client')
stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
stage = base / ('build-preview-stage-' + stamp)
backup = base / ('build-preview-previous-' + stamp)
shutil.copytree(source, stage)
for chunk in (base / 'build/js').glob('chunk-*.js'):
    if not (stage / 'js' / chunk.name).exists():
        shutil.copy2(chunk, stage / 'js' / chunk.name)
(base / 'build').rename(backup)
try:
    stage.rename(base / 'build')
except Exception:
    backup.rename(base / 'build')
    raise
print('Pubblicato. Versione precedente:', backup)
