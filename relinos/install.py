import subprocess
import sys
from pathlib import Path
import platform
import os
import urllib.request
import json
import zipfile
import shutil
import tempfile
import logging

ANSI_CLEAR = "\033[0m"
ANSI_GREEN = "\033[32m"
ANSI_RED = "\033[31m"

class UnsupportedOS(Exception):
    pass

logger = logging.getLogger(__name__)

def getDefaultChromiumLocation() -> tuple[str, Exception|None]:
    osName = platform.system()

    browserPaths = {
        'Windows': [
            str(Path.home()) + '/.relinos/chrome/chrome.exe',
            r'C:\Program Files\Google\Chrome\Application\chrome.exe',
            r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
        ],
        'Linux': [
            str(Path.home) + '/.relinos/chrome/chrome',
            '/usr/bin/google-chrome',
            '/usr/bin/google-chrome-stable',
        ],
        'Darwin': [
            str(Path.home) + '/.relinos/chrome/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing',
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        ],
    }

    browserPathsOS = browserPaths.get(osName)

    if not browserPathsOS:
        logger.error(f'Unsupported OS: {osName}')
        return "", UnsupportedOS(f'Unsupported OS: {osName}')

    for path in browserPathsOS:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path, None

    return "", ValueError(f'No valid browser path found in: {browserPathsOS}')

def createEnv() -> None:
    venvPath = Path.home() / ".relinos" / "env"
    venvPath.mkdir(parents=True, exist_ok=True)

    subprocess.run([sys.executable, "-m", "venv", str(venvPath)], check=True)

    subprocess.run(
        [str(venvPath / "bin" / "pip"), "install", "-r", "requirements.txt"],
        check=True,
    )

def installChrome() -> None:
    '''Installs Google Chrome on Windows, macOS and Linux into ~/.relinos/chrome.'''
    osName = platform.system().lower()
    arch = platform.machine().lower()

    # map to chromes names for different operating systems 
    platforms = {
        "darwin": {
            "arm64": "mac-arm64", "aarch64": "mac-arm64",
            "x86_64": "mac-x64", "amd64": "mac-x64",
        },
        "linux": {
            "x86_64": "linux64", "amd64": "linux64",
        },
        "windows": {
            "x86_64": "win64", "amd64": "win64",
            "arm64": "win64", "aarch64": "win64",
            "x86": "win32", "i386": "win32", "i686": "win32",
        },
    }

    try: osFullName = platforms[osName][arch]
    except KeyError: raise UnsupportedOS(f"Unsupported platform: {osName} {arch}")

    chromeVersionsUrl = "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json"
    url = ""
    try:
        with urllib.request.urlopen(chromeVersionsUrl, timeout=20) as resp: 
            data = json.loads(resp.read())

        for c in data["channels"]["Stable"]["downloads"]["chrome"]:
            if c["platform"] == osFullName: url = c["url"]
    except (urllib.error.URLError, ValueError, KeyError) as e:
        raise Exception("Could not find any chrome download links")

    if not url: raise Exception(f"Could not find chrome download link for os {osFullName}")

    print(f"Downloading {url}")
    with tempfile.TemporaryDirectory() as tmp:
        zipPath = Path(tmp) / "chrome.zip"
        unzipPath = Path(tmp) / "chrome"

        urllib.request.urlretrieve(url, zipPath)

        print(f"Unpacking {url}")
        with zipfile.ZipFile(zipPath, "r") as z:
            z.extractall(unzipPath)
            # this keeps permissions intact, important otherwise the browser cannot be started
            for member in z.infolist():
                mode = (member.external_attr >> 16) & 0o777

                if mode:
                    path = os.path.join(unzipPath, member.filename); os.chmod(path, mode)

        chromePath = Path.home() / ".relinos" / "chrome"

        if os.path.exists(chromePath): shutil.rmtree(chromePath)
        shutil.move(unzipPath / f"chrome-{osFullName}", chromePath)

if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    print("Installing relinos\n")
    createEnv()

    print("Installing Google Chrome")
    try:
        installChrome()
    except:
        print("Could not install Google Chrome, please install it yourself"); raise

    _, err = getDefaultChromiumLocation()
    if err:
        print(f"{ANSI_RED}Missing Google Chrome{ANSI_CLEAR}\nGo to https://www.google.com/chrome/ and follow the instructions")
        print(f"On Linux point the chrome/chromium binary at /usr/bin/google-chrome")
    else:
        print(f"{ANSI_GREEN}Everything is installed {ANSI_CLEAR}")
        print("run: bash relinos/start.sh")

