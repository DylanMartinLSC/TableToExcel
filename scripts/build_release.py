from pathlib import Path
import os
from release_common import freeze, launch_check, server_check, archive
tesseract = Path(os.environ.get('TESSERACT_ROOT', r'C:\Program Files\Tesseract-OCR'))
if not (tesseract / 'tesseract.exe').is_file() or not (tesseract / 'tessdata' / 'eng.traineddata').is_file():
    raise RuntimeError('Tesseract executable and English data are required')
folder = freeze('portable.py', 'TableToExcel', '--collect-all', 'streamlit', '--collect-all', 'img2table',
                '--collect-all', 'pypdfium2', '--copy-metadata', 'streamlit',
                '--add-data', 'app.py;.', '--add-data', 'converter.py;.', '--add-data', 'LICENSE;.',
                '--add-data', f'{tesseract};tesseract')
launch_check(folder / 'TableToExcel.exe', '--check-ocr')
server_check(folder / 'TableToExcel.exe', 8501, '--smoke-test')
archive(folder, 'TableToExcel-windows.zip')
