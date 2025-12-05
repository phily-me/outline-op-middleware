import os
import hmac
import hashlib
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from dotenv import load_dotenv

load_dotenv()

# --- OpenProject ---
OP_BASE_URL = os.getenv("OP_BASE_URL")
OP_API_KEY = os.getenv("OP_API_KEY")
OP_WEBHOOK_SECRET = os.getenv("OP_WEBHOOK_SECRET")
OP_CF_KB_REQUEST = os.getenv("OP_CF_KB_REQUEST")  # Boolean "KB anfordern"
OP_CF_KB_LINK = os.getenv("OP_CF_KB_LINK")  # Text "KB Link"

# --- Outline ---
OUTLINE_BASE_URL = os.getenv("OUTLINE_BASE_URL")
OUTLINE_API_KEY = os.getenv("OUTLINE_API_KEY")
OUTLINE_COLLECTION_ID = os.getenv("OUTLINE_COLLECTION_ID")
OUTLINE_TEMPLATE_ID = os.getenv("OUTLINE_TEMPLATE_ID")


@asynccontextmanager
async def lifespan(app: FastAPI):
    required_vars = {
        "OP_BASE_URL": OP_BASE_URL,
        "OP_API_KEY": OP_API_KEY,
        "OP_WEBHOOK_SECRET": OP_WEBHOOK_SECRET,
        "OP_CF_KB_REQUEST": OP_CF_KB_REQUEST,
        "OP_CF_KB_LINK": OP_CF_KB_LINK,
        "OUTLINE_BASE_URL": OUTLINE_BASE_URL,
        "OUTLINE_API_KEY": OUTLINE_API_KEY,
        "OUTLINE_COLLECTION_ID": OUTLINE_COLLECTION_ID,
        "OUTLINE_TEMPLATE_ID": OUTLINE_TEMPLATE_ID,
    }

    missing = [key for key, value in required_vars.items() if not value]
    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    yield


app = FastAPI(lifespan=lifespan)


def verify_signature(payload_body: bytes, signature: str | None) -> bool:
    """Verifiziert die OpenProject Webhook-Signatur."""
    if not signature or not OP_WEBHOOK_SECRET:
        return False

    expected = hmac.new(
        OP_WEBHOOK_SECRET.encode(), payload_body, hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


async def get_outline_template() -> str:
    """Holt den Content des Outline Templates."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{OUTLINE_BASE_URL}/api/documents.info",
            json={"id": OUTLINE_TEMPLATE_ID},
            headers={
                "Authorization": f"Bearer {OUTLINE_API_KEY}",
                "Content-Type": "application/json",
            },
        )

        if response.status_code != 200:
            raise Exception(f"Failed to fetch template: {response.text}")

        return response.json().get("data", {}).get("text", "")


async def create_outline_document(title: str, content: str) -> str:
    """Erstellt ein Dokument in Outline und gibt die URL zurück."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{OUTLINE_BASE_URL}/api/documents.create",
            json={
                "title": title,
                "text": content,
                "collectionId": OUTLINE_COLLECTION_ID,
                "publish": True,
            },
            headers={
                "Authorization": f"Bearer {OUTLINE_API_KEY}",
                "Content-Type": "application/json",
            },
        )

        if response.status_code != 200:
            raise Exception(f"Failed to create document: {response.text}")

        data = response.json().get("data", {})
        # Vollständige URL zusammenbauen
        return f"{OUTLINE_BASE_URL}{data.get('url', '')}"


async def update_openproject_wp(
    wp_id: int, wp_self_link: str, lock_version: int, kb_url: str
):
    """Updated das Work Package in OpenProject mit der KB URL und setzt das Boolean zurück."""
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"{OP_BASE_URL}{wp_self_link}",
            json={
                "lockVersion": lock_version,
                OP_CF_KB_LINK: kb_url,
                OP_CF_KB_REQUEST: False,  # Boolean zurücksetzen
            },
            auth=("apikey", OP_API_KEY),
            headers={"Content-Type": "application/json"},
        )

        if response.status_code != 200:
            raise Exception(f"Failed to update WP: {response.text}")

        return response.json()


async def process_kb_request(payload: dict):
    """Hauptlogik: Template holen, Dokument erstellen, OP updaten."""
    try:
        wp = payload.get("work_package", {})
        wp_id = wp.get("id")
        wp_subject = wp.get("subject")
        wp_description = wp.get("description", {}).get("raw", "")
        wp_self_link = wp.get("_links", {}).get("self", {}).get("href")
        lock_version = wp.get("lockVersion")

        if not all([wp_id, wp_subject, wp_self_link, lock_version is not None]):
            print(f"Fehler: Unvollständige WP-Daten: id={wp_id}, subject={wp_subject}")
            return

        print(f"Verarbeite KB-Anforderung für WP #{wp_id}: {wp_subject}")

        # 1. Template aus Outline holen
        template_content = await get_outline_template()

        # 2. Template mit WP-Daten anreichern
        content = template_content
        content = content.replace("{{WP_ID}}", str(wp_id))
        content = content.replace("{{WP_SUBJECT}}", wp_subject)
        content = content.replace("{{WP_DESCRIPTION}}", wp_description or "—")
        content = content.replace("{{WP_URL}}", f"{OP_BASE_URL}/work_packages/{wp_id}")

        # Backlink am Ende hinzufügen falls nicht im Template
        if "{{WP_URL}}" not in template_content:
            content += f"\n\n---\n**OpenProject:** [WP #{wp_id}]({OP_BASE_URL}/work_packages/{wp_id})"

        # 3. Dokument in Outline erstellen
        doc_url = await create_outline_document(wp_subject, content)
        print(f"Outline Dokument erstellt: {doc_url}")

        # 4. OpenProject updaten (URL setzen, Boolean zurücksetzen)
        await update_openproject_wp(wp_id, wp_self_link, lock_version, doc_url)
        print(f"WP #{wp_id} erfolgreich aktualisiert mit KB-Link")

    except Exception as e:
        print(f"Fehler bei der Verarbeitung: {e}")


@app.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    """Webhook-Endpunkt für OpenProject."""

    # 1. Raw body für Signatur-Prüfung
    body = await request.body()

    # 2. Signatur verifizieren
    signature = request.headers.get("X-OP-Signature")
    if not verify_signature(body, signature):
        print("Webhook-Signatur ungültig")
        raise HTTPException(status_code=401, detail="Invalid signature")

    # 3. Payload parsen
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    action = payload.get("action")

    # 4. Nur auf work_package:updated reagieren
    if action != "work_package:updated":
        return {"status": "ignored", "reason": f"action '{action}' not relevant"}

    # 5. Prüfen ob "KB anfordern" == True
    wp = payload.get("work_package", {})
    kb_requested = wp.get(OP_CF_KB_REQUEST, False)
    kb_link_exists = wp.get(OP_CF_KB_LINK)

    if not kb_requested:
        return {"status": "ignored", "reason": "kb_request not set"}

    if kb_link_exists:
        print(f"WP #{wp.get('id')} hat bereits einen KB-Link, überspringe")
        return {"status": "ignored", "reason": "kb_link already exists"}

    # 6. Verarbeitung im Hintergrund starten
    background_tasks.add_task(process_kb_request, payload)

    return {"status": "processing_started", "wp_id": wp.get("id")}


@app.get("/")
def health_check():
    return {"status": "ok", "service": "outline-op-middleware"}
