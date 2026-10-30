"""Portable Streamlit entry point; native OCR stays beside the application."""
import os
from pathlib import Path
import sys

def configure():
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
    native = root / 'tesseract'
    if native.is_dir():
        os.environ['PATH'] = str(native) + os.pathsep + os.environ.get('PATH', '')
        os.environ['TESSDATA_PREFIX'] = str(native / 'tessdata')
    return root

if __name__ == '__main__':
    from multiprocessing import freeze_support
    freeze_support()
    root = configure()
    if '--check-ocr' in sys.argv:
        import tempfile
        import subprocess
        from PIL import Image, ImageDraw, ImageFont
        from converter import setup_tesseract
        setup_tesseract()
        with tempfile.TemporaryDirectory() as d:
            image = Image.new('RGB', (900, 180), 'white')
            draw = ImageDraw.Draw(image)
            font = ImageFont.truetype(str(Path(os.environ['WINDIR']) / 'Fonts' / 'arial.ttf'), 72)
            draw.text((30, 30), '12345', fill='black', font=font)
            path = Path(d) / 'ocr.png'
            image.save(path)
            result = subprocess.run(['tesseract', str(path), 'stdout', '-l', 'eng', '--psm', '7'],
                                    check=True, capture_output=True, text=True)
            assert '12345' in result.stdout, result.stdout
        sys.exit(0)
    from streamlit.web import cli
    sys.argv = ['streamlit', 'run', str(root / 'app.py'), '--server.address=127.0.0.1',
                '--server.port=8501', '--browser.gatherUsageStats=false',
                '--server.headless=' + ('true' if '--smoke-test' in sys.argv else 'false'),
                '--global.developmentMode=false']
    sys.exit(cli.main())
