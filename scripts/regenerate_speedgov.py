"""Regenera offline os bindings Speedgov a partir dos XSDs versionados."""
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = ROOT / 'pynfe/data/XSDs/NFS-e/Speedgov'
PACKAGE = Path('pynfe/utils/nfse/speedgov')


def main():
    executable = Path(sys.executable).parent / 'pyxbgen'
    with tempfile.TemporaryDirectory(prefix='speedgov-bindings-') as tmp:
        args = [str(executable), '--module-prefix=pynfe.utils.nfse.speedgov', '--binding-root=' + tmp]
        for schema in sorted(SCHEMAS.glob('*.xsd')):
            name = {'tipos_v1': '_tipos', 'xmldsig-core-schema20020212_v1': '_dsig'}.get(schema.stem, schema.stem.replace('_v1', '_v01'))
            args.extend(['-u', str(schema), '-m', name])
        subprocess.run(args, check=True, cwd=ROOT)
        generated = Path(tmp) / PACKAGE
        for source in generated.glob('*.py'):
            if source.name != '__init__.py':
                text = source.read_text().replace(str(ROOT) + '/', '').replace(str(Path(tmp)) + '/', '')
                (ROOT / PACKAGE / source.name).write_text(text)
        print('Bindings Speedgov regenerados a partir dos schemas locais.')


if __name__ == '__main__':
    main()
