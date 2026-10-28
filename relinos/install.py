import subprocess
import sys
from pathlib import Path
import platform
import os
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
            r'C:\Program Files\Google\Chrome\Application\chrome.exe',
            r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
        ],
        'Linux': [
            '/usr/bin/google-chrome',
            '/usr/bin/google-chrome-stable',
        ],
        'Darwin': [
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

os.system('cls' if os.name == 'nt' else 'clear')
print("Installing relinos\n")
createEnv()

_, err = getDefaultChromiumLocation()
if err:
    print(f"{ANSI_RED}Missing Google Chrome{ANSI_CLEAR}\nGo to https://www.google.com/chrome/ and follow the instructions")
else:
    print(f"{ANSI_GREEN}Everything is installed {ANSI_CLEAR}")
    print("run: bash relinos/startup.sh")
