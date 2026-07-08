from dotenv import load_dotenv

load_dotenv()

from zeppelinker.bot import main  # noqa: E402  (must load .env before this import)

if __name__ == "__main__":
    main()
