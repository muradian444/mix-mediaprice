# -*- coding: utf-8 -*-
"""Google Drive-ի միացում MP3 հղումների համար (մեկ անգամ).
1) Google Cloud Console -> APIs & Services -> Enable «Google Drive API»
2) Credentials -> Create credentials -> OAuth client ID -> Desktop app -> Download JSON
3) JSON-ը պահեք բոտի թղթապանակում credentials.json անունով
4) Գործարկեք՝  python drive_login.py   (կբացվի բրաուզերը, մտեք Google հաշիվ և թույլատրեք)
Կստեղծվի data/drive_token.json, և բոտը MP3-ները կվերբեռնի «Mix Media MP3» թղթապանակ՝ հղումով."""
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from mp3link import CLIENT, SCOPES, TOKEN

if not Path(CLIENT).exists():
    raise SystemExit(f"Չգտա {CLIENT}. Ներբեռնեք OAuth client JSON-ը և պահեք credentials.json անունով")
creds = InstalledAppFlow.from_client_secrets_file(str(CLIENT), SCOPES).run_local_server(port=0)
TOKEN.parent.mkdir(exist_ok=True)
TOKEN.write_text(creds.to_json(), encoding="utf-8")
print("✅ Google Drive-ը միացված է:", TOKEN)
