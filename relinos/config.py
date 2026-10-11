from os import environ, getenv

mainPort = int(getenv("PORT", "8031"))

serverName = environ.get("SERVER_NAME", f"http://127.0.0.1:{mainPort}")

storageDirPath = f"{environ['HOME']}/.relinos/storage"
dbPath = f"{environ['HOME']}/.relinos/storage/main.db"

cacheDirPath = f"{environ['HOME']}/.relinos/cache"
cacheDBPath = f"{environ['HOME']}/.relinos/cache/cache.db"

debugDirPath = f"{environ['HOME']}/.relinos/debug"

dumpDirPath = f"{environ['HOME']}/.relinos/dump"

openaiAPIKey = getenv("OPENAI_API_KEY", "")
