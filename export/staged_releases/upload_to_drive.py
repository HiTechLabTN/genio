#!/usr/bin/env python3
"""Drive workaround — Partie A/B/C/D staging uploader (standalone, stdlib+requests).

zenskill est absent sur cette machine : on ne peut pas uploader via le skill.
Stratégie directive :
  1. Tout livrable est stagé dans /data/ai_tools/genio/export/staged_releases/.
  2. Ce script upload le dossier stagé vers Google Drive :
     - si GOOGLE_SERVICE_ACCOUNT_JSON existe → Drive API (service account) ;
     - elif GOOGLE_OAUTH_TOKEN existe → upload simple (Bearer) ;
     - sinon → affiche l'instruction : exposer le dossier via un endpoint
       du Sovereign Cockpit pour téléchargement local (download manuel).

Usage :
    python3 upload_to_drive.py [staged_dir] [drive_folder_id]
"""
import json
import mimetypes
import os
import sys
import urllib.request

STAGED_DEFAULT = "/data/ai_tools/genio/export/staged_releases/v2_sovereign"


def _upload_simple_bearer(token: str, path: str, folder_id: str | None) -> str:
    meta = {"name": os.path.basename(path)}
    if folder_id:
        meta["parents"] = [folder_id]
    boundary = "genio-boundary-001"
    data = open(path, "rb").read()
    mime, _ = mimetypes.guess_type(path)
    body = (
        f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{json.dumps(meta)}\r\n"
        f"--{boundary}\r\nContent-Type: {mime or 'application/octet-stream'}\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
        data=body,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": f"multipart/related; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r).get("id", "")


def main() -> int:
    staged = sys.argv[1] if len(sys.argv) > 1 else STAGED_DEFAULT
    folder_id = sys.argv[2] if len(sys.argv) > 2 else os.getenv("GENIO_DRIVE_FOLDER_ID")
    files = sorted(f for f in os.listdir(staged)
                   if os.path.isfile(os.path.join(staged, f)))
    print(f"staged: {staged} ({len(files)} fichiers)")
    sa = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    token = os.getenv("GOOGLE_OAUTH_TOKEN")
    if sa and os.path.exists(sa):
        print("service account détecté — échange JWT→access token non implémenté "
              "en stdlib seule ; utilisez gcloud ou renseignez GOOGLE_OAUTH_TOKEN.")
        return 2
    if token:
        for f in files:
            fid = _upload_simple_bearer(token, os.path.join(staged, f), folder_id)
            print(f"  uploaded {f} → id={fid}")
        print("UPLOAD OK via OAuth Bearer.")
        return 0
    print("AUCUN credential Drive (GOOGLE_OAUTH_TOKEN / service account).")
    print("Fallback directive : exposez ce dossier via un endpoint du Sovereign")
    print(f"Cockpit en servant : {staged}")
    print("  ex: GET /api/releases/v2_sovereign/<fichier> → téléchargement local,")
    print("  puis upload manuel vers Drive depuis le poste AZMI.")
    for f in files:
        print(f"  - {f}")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
