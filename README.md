# zeppelinker

Telegram bot to replace social media links with their improved preview variants. The mapping of supported link types to what services are used to "fix" these links is given below.

| Link type | Fix mechanism |
|-----------|---------------|
| [Accelerated Mobile Pages (AMP)](https://amp.dev) | [AmputatorBot](https://www.amputatorbot.com/) |
| [Instagram](https://instagram.com) | [instagramez (embedez)](https://instagramez.com/) |
| [Medium](https://medium.com) | [LibMedium](https://git.batsense.net/realaravinth/libmedium) |
| [Reddit](https://reddit.com) | [FxReddit](https://github.com/MinnDevelopment/fxreddit) |
| [TikTok](https://tiktok.com) | [fxTikTok](https://github.com/okdargy/fxtiktok) |
| [Twitter](https://twitter.com) / [X](https://x.com) | [TweetFix](https://github.com/FixTweet/FixTweet) |
| [YouTube Shorts](https://www.youtube.com/shorts) | Rewrite URL to normal YouTube player |

It also replies with a summary from [HowLongToBeat](https://howlongtobeat.com) when mentioned with `hltb <game name>` (or plain `hltb <game name>` in a private chat).

Rewritten in Python (originally Rust, see git history) using [python-telegram-bot](https://python-telegram-bot.org/).

## Development

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.sample .env  # fill in real values
python main.py
```

## Deployment

### fly.io

Refer to the environment variables in `.env.sample` and set them as secrets on your fly.io app
(`fly secrets set NAME=value`). The bundled `fly.toml` refers to the maintainer's own deployment,
swap out `app` for your own unique name.

### Docker

```
docker build -t zeppelinker .
docker run --env-file .env zeppelinker
```
