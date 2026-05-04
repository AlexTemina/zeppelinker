use crate::{AsyncError, bot_ext::BotExt};
use regex::Regex;
use reqwest::header::{HeaderMap, HeaderValue, ORIGIN, REFERER, USER_AGENT};
use serde_json::Value;
use std::sync::LazyLock;
use teloxide::{
    Bot,
    payloads::SendPhotoSetters,
    prelude::Requester,
    types::{
        ChatAction, InputFile, Me, Message, MessageEntity, MessageEntityKind, ParseMode,
        ReplyParameters, UserId,
    },
};
use url::Url;

const HLTB_USER_AGENT: &str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";

static HLTB_HTTP: LazyLock<reqwest::Client> = LazyLock::new(|| {
    reqwest::Client::builder()
        .user_agent(HLTB_USER_AGENT)
        .build()
        .expect("HLTB reqwest client")
});

const HLTB_ORIGIN: &str = "https://howlongtobeat.com";

/// Lowercase `@handle` without `@`, from the same [`Me`] the dispatcher injects (see `filter_command`).
fn bot_handle_lc(me: &Me) -> Option<String> {
    me.user
        .username
        .as_deref()
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(str::to_lowercase)
        .or_else(|| {
            std::env::var("BOT_NAME")
                .ok()
                .map(|s| s.trim_start_matches('@').trim().to_lowercase())
                .filter(|s| !s.is_empty())
        })
}

fn message_text_and_entities(msg: &Message) -> Option<(&str, &[MessageEntity])> {
    if let Some(t) = msg.text() {
        let e = msg.entities().unwrap_or(&[]);
        return Some((t, e));
    }
    if let Some(t) = msg.caption() {
        let e = msg.caption_entities().unwrap_or(&[]);
        return Some((t, e));
    }
    None
}

fn bleed_json_headers() -> HeaderMap {
    let mut m = HeaderMap::new();
    m.insert(
        USER_AGENT,
        HeaderValue::from_static(HLTB_USER_AGENT),
    );
    m.insert(ORIGIN, HeaderValue::from_static(HLTB_ORIGIN));
    m.insert(REFERER, HeaderValue::from_static("https://howlongtobeat.com/"));
    m.insert(
        reqwest::header::CONTENT_TYPE,
        HeaderValue::from_static("application/json"),
    );
    m.insert(
        reqwest::header::ACCEPT,
        HeaderValue::from_static("application/json"),
    );
    m
}

/// `tg://user?id=…` mentions (common when picking the bot from the mention UI).
fn text_link_is_bot(url: &reqwest::Url, bot_id: UserId) -> bool {
    if url.scheme() != "tg" || url.host_str() != Some("user") {
        return false;
    }
    url.query_pairs().any(|(k, v)| {
        k == "id" && v.parse::<u64>().ok() == Some(bot_id.0)
    })
}

fn utf16_slice(text: &str, offset: usize, length: usize) -> Option<String> {
    let utf16: Vec<u16> = text.encode_utf16().collect();
    let slice = utf16.get(offset..offset + length)?;
    Some(String::from_utf16_lossy(slice))
}

fn tail_utf16(text: &str, start_utf16: usize) -> Option<String> {
    let utf16: Vec<u16> = text.encode_utf16().collect();
    let slice = utf16.get(start_utf16..)?;
    Some(String::from_utf16_lossy(slice))
}

fn parse_tail_for_query(tail: &str) -> Option<String> {
    let mut parts = tail.trim_start().split_whitespace();
    let first = parts.next()?;
    if !first.eq_ignore_ascii_case("hltb") {
        return None;
    }
    let query: String = parts.collect::<Vec<_>>().join(" ");
    (!query.is_empty()).then_some(query)
}

fn parse_from_entities(message: &Message, me: &Me) -> Option<String> {
    let (text, entities) = message_text_and_entities(message)?;
    let bot_name_lc = bot_handle_lc(me);
    let bot_id = crate::bot_ext::telegram_bot_user_id();

    for entity in entities {
        let mention_is_bot = match &entity.kind {
            MessageEntityKind::Mention => {
                let Some(ref name_lc) = bot_name_lc else {
                    continue;
                };
                let slice = utf16_slice(text, entity.offset, entity.length)?;
                let user = slice.strip_prefix('@')?.to_lowercase();
                user == *name_lc
            }
            MessageEntityKind::TextMention { user } => user.id == bot_id,
            MessageEntityKind::TextLink { url } => text_link_is_bot(url, bot_id),
            _ => false,
        };

        if !mention_is_bot {
            continue;
        }

        let tail = tail_utf16(text, entity.offset + entity.length)?;
        return parse_tail_for_query(&tail);
    }

    None
}

fn parse_with_regex(text: &str, me: &Me) -> Option<String> {
    let bot = bot_handle_lc(me)?;
    if bot.is_empty() {
        return None;
    }
    let escaped = regex::escape(&bot);
    let nbsp = "\u{00a0}";
    // Allow text before the mention (common in groups: "hey @bot hltb …").
    let re = Regex::new(&format!(
        r"(?i)(?:^|\s)@{escaped}(?:\s|{nbsp})+hltb(?:\s|{nbsp})+(.+)$"
    ))
    .ok()?;
    let caps = re.captures(text.trim())?;
    let q = caps.get(1).map(|m| m.as_str().trim())?;
    (!q.is_empty()).then_some(q.to_owned())
}

/// In private chat only: plain `hltb The Last of Us 2` (no @mention) for quick testing.
fn parse_private_plain_hltb(message: &Message) -> Option<String> {
    if !message.chat.is_private() {
        return None;
    }
    let text = message.text().or_else(|| message.caption())?.trim();
    if text.starts_with('/') {
        return None;
    }
    let mut parts = text.split_whitespace();
    let first = parts.next()?;
    if !first.eq_ignore_ascii_case("hltb") {
        return None;
    }
    let q = parts.collect::<Vec<_>>().join(" ");
    (!q.is_empty()).then_some(q)
}

/// `@bot hltb …` (entities or regex), `TextMention` / `tg://user` links, or private `hltb …`.
/// `me` must be the dispatcher-injected [`Me`] (same source as command parsing).
pub(crate) fn parse_hltb_query(message: &Message, me: &Me) -> Option<String> {
    parse_from_entities(message, me)
        .or_else(|| {
            let text = message.text().or_else(|| message.caption())?;
            parse_with_regex(text, me)
        })
        .or_else(|| parse_private_plain_hltb(message))
}

pub(crate) fn matches(message: &Message, me: &Me) -> bool {
    parse_hltb_query(message, me).is_some()
}

fn escape_html(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
}

struct HltbGame {
    title: String,
    main: String,
    extra: String,
    completionist: String,
    /// Cover art for the first hit (HLTB `game_image` → `/games/...`).
    cover_url: Option<String>,
}

/// HLTB `/api/bleed` search rows use `comp_*` in **seconds** (integer or float in `serde_json::Number`).
fn format_hltb_seconds(seconds: i64) -> String {
    if seconds <= 0 {
        return "—".to_string();
    }
    if seconds < 60 {
        return "<1m".to_string();
    }
    let hours = seconds / 3600;
    let mins = (seconds % 3600) / 60;
    match (hours, mins) {
        (0, _) => format!("{mins}m"),
        (_, 0) => format!("{hours}h"),
        _ => format!("{hours}h {mins}m"),
    }
}

fn json_seconds_field(obj: &Value, key: &str) -> String {
    let Some(v) = obj.get(key) else {
        return "—".to_string();
    };
    if let Some(s) = v.as_str() {
        return s.to_string();
    }
    let secs = v
        .as_i64()
        .or_else(|| v.as_u64().and_then(|u| i64::try_from(u).ok()))
        .or_else(|| {
            v.as_f64()
                .filter(|f| f.is_finite())
                .map(|f| f.round() as i64)
        });
    secs.map_or("—".to_string(), format_hltb_seconds)
}

fn games_from_data_array(data: &[Value]) -> Vec<HltbGame> {
    let mut games = Vec::new();
    for item in data.iter().take(10) {
        let title = item
            .get("game_name")
            .and_then(|v| v.as_str())
            .unwrap_or("?")
            .to_string();
        let main = json_seconds_field(item, "comp_main");
        let extra = json_seconds_field(item, "comp_plus");
        let completionist = json_seconds_field(item, "comp_100");
        let cover_url = item
            .get("game_image")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
            .map(|img| format!("{HLTB_ORIGIN}/games/{img}"));
        games.push(HltbGame {
            title,
            main,
            extra,
            completionist,
            cover_url,
        });
    }
    games
}

fn parse_search_response(body: &str) -> Option<Vec<HltbGame>> {
    let v: Value = serde_json::from_str(body).ok()?;
    let data = v.get("data").and_then(|d| d.as_array())?;
    Some(games_from_data_array(data))
}

/// Same shape as the site's `fetch("/api/bleed", …)` body (see Next.js bundles).
fn build_bleed_search_json(search_terms: &[String]) -> Value {
    serde_json::json!({
        "searchType": "games",
        "searchTerms": search_terms,
        "searchPage": 1,
        "size": 20,
        "searchOptions": {
            "games": {
                "userId": 0,
                "platform": "",
                "sortCategory": "popular",
                "rangeCategory": "main",
                "rangeTime": { "min": 0, "max": 0 },
                "gameplay": { "perspective": "", "flow": "", "genre": "", "difficulty": "" },
                "rangeYear": { "min": "", "max": "" },
                "modifier": ""
            },
            "users": { "sortCategory": "postcount" },
            "lists": { "sortCategory": "follows" },
            "filter": "",
            "sort": 0,
            "randomizer": 0
        },
        "useCache": true
    })
}

struct BleedCreds {
    token: String,
    hp_key: String,
    hp_val: String,
}

async fn fetch_bleed_init() -> Option<BleedCreds> {
    let ts = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0);
    let url = format!("{HLTB_ORIGIN}/api/bleed/init?t={ts}");
    let res = HLTB_HTTP
        .get(&url)
        .headers(bleed_json_headers())
        .send()
        .await
        .ok()?;
    if !res.status().is_success() {
        tracing::warn!(url = %url, status = %res.status(), "HLTB bleed/init HTTP error");
        return None;
    }
    let v: Value = res.json().await.ok()?;
    let token = v.get("token").and_then(|x| x.as_str())?.to_string();
    let hp_key = v.get("hpKey").and_then(|x| x.as_str())?.to_string();
    let hp_val = v.get("hpVal").and_then(|x| x.as_str())?.to_string();
    if token.is_empty() || hp_key.is_empty() || hp_val.is_empty() {
        tracing::warn!("HLTB bleed/init: missing token/hpKey/hpVal");
        return None;
    }
    Some(BleedCreds {
        token,
        hp_key,
        hp_val,
    })
}

async fn post_bleed_search(creds: &BleedCreds, search_terms: &[String]) -> Option<reqwest::Response> {
    let mut body = build_bleed_search_json(search_terms);
    if let Value::Object(ref mut map) = body {
        map.insert(
            creds.hp_key.clone(),
            Value::String(creds.hp_val.clone()),
        );
    }

    let token_h = HeaderValue::from_str(&creds.token).ok()?;
    let key_h = HeaderValue::from_str(&creds.hp_key).ok()?;
    let val_h = HeaderValue::from_str(&creds.hp_val).ok()?;

    let mut headers = bleed_json_headers();
    headers.insert(
        reqwest::header::HeaderName::from_static("x-auth-token"),
        token_h,
    );
    headers.insert(
        reqwest::header::HeaderName::from_static("x-hp-key"),
        key_h,
    );
    headers.insert(
        reqwest::header::HeaderName::from_static("x-hp-val"),
        val_h,
    );

    HLTB_HTTP
        .post(format!("{HLTB_ORIGIN}/api/bleed"))
        .headers(headers)
        .json(&body)
        .send()
        .await
        .ok()
}

/// Official site flow (mirrors browser): `GET /api/bleed/init` then `POST /api/bleed` with auth + hp headers and dynamic JSON field `{hpKey: hpVal}`.
async fn search_howlongtobeat_bleed(search_terms: &[String]) -> Option<Vec<HltbGame>> {
    let mut creds = fetch_bleed_init().await?;

    for attempt in 0..2u8 {
        let res = post_bleed_search(&creds, search_terms).await?;

        let status = res.status();
        if status == reqwest::StatusCode::FORBIDDEN && attempt == 0 {
            tracing::warn!("HLTB bleed 403, refreshing token");
            creds = fetch_bleed_init().await?;
            continue;
        }

        if !status.is_success() {
            tracing::warn!(status = %status, "HLTB bleed search HTTP error");
            return None;
        }

        let text = res.text().await.ok()?;
        return parse_search_response(&text);
    }

    None
}

async fn search_games(query: &str) -> Result<Vec<HltbGame>, AsyncError> {
    let search_terms: Vec<String> = query.split_whitespace().map(str::to_string).collect();
    if search_terms.is_empty() {
        return Ok(vec![]);
    }

    if let Some(games) = search_howlongtobeat_bleed(&search_terms).await {
        if !games.is_empty() {
            return Ok(games);
        }
    }

    Ok(vec![])
}

fn site_search_url(query: &str) -> String {
    let enc: String = url::form_urlencoded::byte_serialize(query.as_bytes()).collect();
    format!("https://howlongtobeat.com/?q={enc}")
}

fn games_reply_html(games: &[HltbGame]) -> String {
    let mut out = String::from("<b>HowLongToBeat</b>\n\n");
    for (i, g) in games.iter().take(5).enumerate() {
        if i > 0 {
            out.push('\n');
        }
        out.push_str(&format!(
            "<b>{}</b>\nMain: {}\n+ Extras: {}\nCompletionist: {}\n",
            escape_html(&g.title),
            escape_html(&g.main),
            escape_html(&g.extra),
            escape_html(&g.completionist),
        ));
    }
    if games.len() > 5 {
        out.push_str(&format!("\n… and {} more.", games.len() - 5));
    }
    out.push_str("\n<i>Data from howlongtobeat.com (unofficial).</i>");
    out
}

/// Telegram photo captions are limited to 1024 characters after parsing.
fn truncate_caption_html(s: &str, max_bytes: usize) -> String {
    if s.len() <= max_bytes {
        return s.to_string();
    }
    let mut out = String::new();
    for ch in s.chars() {
        if out.len() + ch.len_utf8() > max_bytes.saturating_sub(3) {
            break;
        }
        out.push(ch);
    }
    out.push_str("…");
    out
}

pub async fn handler(bot: Bot, message: Message, me: Me) -> Result<(), AsyncError> {
    let Some(query) = parse_hltb_query(&message, &me) else {
        return Ok(());
    };

    if message
        .from
        .as_ref()
        .is_some_and(|u| u.id == crate::bot_ext::telegram_bot_user_id())
    {
        return Ok(());
    }

    let games = search_games(&query).await?;

    let reply = if games.is_empty() {
        let href = escape_html(&site_search_url(&query));
        format!(
            "No HowLongToBeat results for <i>{}</i>. \
Try on the site: <a href=\"{href}\">howlongtobeat.com</a>.",
            escape_html(&query)
        )
    } else {
        games_reply_html(&games)
    };

    if games.is_empty() {
        bot.try_reply(&message, &reply).await?;
        return Ok(());
    }

    let reply_params = message
        .reply_to_message()
        .map(|r| ReplyParameters::new(r.id))
        .unwrap_or_else(|| ReplyParameters::new(message.id));

    if let Some(cover) = games
        .first()
        .and_then(|g| g.cover_url.as_deref())
        .and_then(|u| Url::parse(u).ok())
    {
        bot.send_chat_action(message.chat.id, ChatAction::UploadPhoto)
            .await?;

        let caption = truncate_caption_html(&reply, 1024);
        let photo_result = bot
            .send_photo(message.chat.id, InputFile::url(cover))
            .caption(caption)
            .parse_mode(ParseMode::Html)
            .reply_parameters(reply_params)
            .await;

        if photo_result.is_ok() {
            return Ok(());
        }
        tracing::warn!("HLTB send_photo failed, sending text only");
    }

    bot.try_reply(&message, &reply).await?;
    Ok(())
}
