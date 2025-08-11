Legit Downloader (Windows-friendly)

This tool downloads files you are authorized to access. It does not bypass DRM or any access controls. Use only in accordance with the source website's terms.

Key features:
- Single URL or list of URLs
- Resume (single-connection) if the server supports Range
- Parallel chunked downloads (faster on large files)
- Retries with exponential backoff
- Custom headers (e.g., Authorization) for authorized content

Usage

1) Install Python 3.10+ and deps:

```
pip install -r requirements.txt
```

2) Run:

```
python legit_downloader.py --url "https://example.com/file.iso"
```

Multiple URLs:
```
python legit_downloader.py --url "https://example.com/a.zip" --url "https://example.com/b.zip"
```

From a list file:
```
python legit_downloader.py --list urls.txt
```

Custom headers (e.g., bearer token):
```
python legit_downloader.py --url "https://example.com/protected.pdf" \
  --header "Authorization: Bearer YOUR_TOKEN" \
  --header "User-Agent: MyDownloader/1.0"
```

Parallel connections and chunk size:
```
python legit_downloader.py --url "https://example.com/big.bin" --connections 8 --chunk-size 8388608
```

Resume for single-connection is on by default. Disable with `--no-resume`.

Windows packaging (optional)

If you want a standalone .exe on Windows, you can package with PyInstaller:

```
pip install pyinstaller
pyinstaller --onefile --name legit-downloader legit_downloader.py
```

The resulting executable will be in `dist/legit-downloader(.exe)`.

Legal notice

- Do not use this tool to attempt to download DRM-protected or encrypted content without permission.
- Respect robots.txt, rate limits, and the website's terms.
- You are responsible for how you use this software.