import json
import os
import sys
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse, parse_qs

import requests

# ------------------------------
# CONFIGURATION
# ------------------------------
FEED_URL = "https://yls8.mtheall.com/ninupdates/feed.php"
# Le webhook est lu depuis le secret GitHub DISCORD_WEBHOOK_URL (jamais en clair dans le code)
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
STATE_FILE = "seen.json"
MAX_SEEN = 300  # nombre de GUID gardés en mémoire

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NinUpdatesBOT/1.0)"}

# ------------------------------
# EMBEDS PAR SYSTÈME
# ------------------------------
# Variables utilisables dans tous les textes :
#   {title}   -> titre complet du flux   (ex. "Switch 2 23.0.1")
#   {version} -> numéro de version seul  (ex. "23.0.1")
#   {system}  -> champ "name" du système
#   {link}    -> lien vers le rapport NinUpdates
#
# Champs image (URL directes vers un .png/.jpg/.gif) :
#   avatar_url  -> avatar du bot
#   author_icon -> petite icône ronde à gauche de l'auteur
#   thumbnail   -> miniature en haut à droite de l'embed
#   image       -> grande image en bas de l'embed
#   footer_icon -> petite icône ronde à gauche du pied de page
#
# Un champ vide ("") n'est pas affiché.
# Les champs absents d'un système reprennent ceux de DEFAULT.
# Seuls les systèmes listés dans SYSTEMS sont postés, les autres sont ignorés.

DEFAULT = {
    "name": "Console Nintendo",
    "username": "",
    "avatar_url": "",
    "content": "",
    "author": "{system}",
    "author_icon": "",
    "title": "🆕 {title}",
    "description": "Nouvelle mise à jour système détectée.",
    "color": 0xE60012,
    "thumbnail": "",
    "image": "",
    "footer": "NinUpdates",
    "footer_icon": "",
}

SYSTEMS = {
    # Mise à jour du firmware - Nintendo Switch
    "hac": {
        "name": "Mise à jour du firmware - Nintendo Switch",
        "title": "🔴 Switch — Firmware {version}",
        "description": "Une nouvelle mise à jour de la **Nintendo Switch** est disponible !\n⚠️ **Veuillez attendre les instructions pour la mise à jour sur une console Atmosphere**",
        "color": 0xE60012,
        "author_icon": "",
        "thumbnail": "",
        "image": "https://homebrewfrance.github.io/cdn/serveur/BANNER_NS2.png",
    },
    # Mise à jour du firmware - Nintendo Switch 2
    "bee": {
        "name": "Mise à jour du firmware - Nintendo Switch 2",
        "title": "🔴 Switch 2 — Firmware {version}",
        "description": "Une nouvelle mise à jour de la **Nintendo Switch 2** est disponible !\n⚠️ **Veuillez attendre les instructions pour la mise à jour sur une console exécutant ns2jb**",
        "color": 0xFF3C28,
        "author_icon": "",
        "thumbnail": "https://homebrewfrance.github.io/cdn/serveur/BANNER_NS2.png",
        "image": "https://homebrewfrance.github.io/cdn/serveur/BANNER_NS2.png",
    },
}

# ------------------------------
# FONCTIONS
# ------------------------------
def load_seen():
    if not os.path.exists(STATE_FILE):
        return None  # premier lancement
    with open(STATE_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_seen(seen):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(seen[-MAX_SEEN:], f, indent=2, ensure_ascii=False)


def fetch_items():
    r = requests.get(FEED_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    items = []
    for item in root.iter("item"):
        link = (item.findtext("link") or "").strip()
        items.append({
            "title": (item.findtext("title") or "").strip(),
            "link": link,
            "guid": (item.findtext("guid") or link).strip(),
            "pubDate": (item.findtext("pubDate") or "").strip(),
        })
    return items  # le flux est du plus récent au plus ancien


def system_code(link):
    return parse_qs(urlparse(link).query).get("sys", [""])[0]


def fill(text, variables):
    try:
        return str(text).format(**variables)
    except (KeyError, IndexError, ValueError):
        return str(text)  # accolade mal formée : on affiche le texte tel quel


def build_message(item):
    cfg = {**DEFAULT, **SYSTEMS.get(system_code(item["link"]), {})}
    parts = item["title"].split()
    variables = {
        "title": item["title"],
        "version": parts[-1] if parts else item["title"],
        "system": cfg["name"],
        "link": item["link"],
    }
    f = {k: fill(v, variables) if isinstance(v, str) else v for k, v in cfg.items()}

    embed = {"url": item["link"], "color": f["color"]}
    if f["title"]:
        embed["title"] = f["title"][:256]
    if f["description"]:
        embed["description"] = f["description"][:4096]
    if f["author"]:
        embed["author"] = {"name": f["author"][:256]}
        if f["author_icon"]:
            embed["author"]["icon_url"] = f["author_icon"]
    if f["thumbnail"]:
        embed["thumbnail"] = {"url": f["thumbnail"]}
    if f["image"]:
        embed["image"] = {"url": f["image"]}
    if f["footer"]:
        embed["footer"] = {"text": f["footer"]}
        if f["footer_icon"]:
            embed["footer"]["icon_url"] = f["footer_icon"]
    try:
        embed["timestamp"] = parsedate_to_datetime(item["pubDate"]).isoformat()
    except (TypeError, ValueError):
        pass

    data = {"embeds": [embed]}
    for key in ("content", "username", "avatar_url"):
        if f[key]:
            data[key] = f[key]
    return data


def send_update(item):
    r = requests.post(WEBHOOK_URL, json=build_message(item), timeout=30)
    if r.status_code in (200, 204):
        print(f"✅ Envoyé : {item['title']}")
        return True
    print(f"❌ Erreur pour {item['title']} : {r.status_code}, {r.text}")
    return False


# ------------------------------
# EXECUTION
# ------------------------------
if __name__ == "__main__":
    if "--preview" in sys.argv:
        # Aperçu local sans rien envoyer : python ninupdates.py --preview
        for code, sample in (("hac", "Switch 23.0.1"), ("bee", "Switch 2 23.0.1")):
            fake = {"title": sample, "link": f"https://yls8.mtheall.com/ninupdates/reports.php?sys={code}",
                    "guid": "", "pubDate": "Thu, 01 Oct 2026 01:02:36 +0000"}
            print(json.dumps(build_message(fake), indent=2, ensure_ascii=False))
        sys.exit(0)

    if not WEBHOOK_URL:
        sys.exit("❌ Secret DISCORD_WEBHOOK_URL manquant.")

    items = fetch_items()
    seen = load_seen()

    if seen is None:
        # Premier lancement : on mémorise tout l'historique sans spammer le salon
        save_seen([i["guid"] for i in reversed(items)])
        print(f"Initialisation : {len(items)} entrées mémorisées, rien n'est envoyé.")
        sys.exit(0)

    new_items = [i for i in reversed(items) if i["guid"] not in seen]  # du plus ancien au plus récent
    if not new_items:
        print("Aucune nouvelle mise à jour.")

    for item in new_items:
        if system_code(item["link"]) not in SYSTEMS:
            print(f"⏭️ Ignoré (système non suivi) : {item['title']}")
            seen.append(item["guid"])
            continue
        if send_update(item):
            seen.append(item["guid"])
        else:
            break  # on réessaiera au prochain passage

    save_seen(seen)
