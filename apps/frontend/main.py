from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
import logging
import httpx
import os

logging.basicConfig(level=logging.INFO, format="[Frontend] %(message)s")

app = FastAPI()
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates")
)


async def _fetch_cowhide_json() -> dict:
    url = "https://secure.runescape.com/m=itemdb_oldschool/api/catalogue/detail.json?item=1739"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as exc:
        logging.error(f"Error fetching cowhide data: {exc}")
        raise


def _format_today_percentage(current_price: int, today_price_field: str) -> str:
    """Compute today's percentage change given current price and a '+x'/'-x' delta string.

    Returns a string like '(+4.5%)' or '' if not computable.
    """
    try:
        raw_delta = str(today_price_field)
        sign = -1 if raw_delta.startswith("-") else 1
        raw_num = raw_delta[1:] if raw_delta[:1] in "+-" else raw_delta
        delta_gp = sign * int(raw_num or 0)
        previous_price = current_price - delta_gp
        if previous_price in (None, 0):
            return ""
        today_pct = (delta_gp / previous_price) * 100.0
        return f"({today_pct:+.1f}%)"
    except Exception:
        return ""


@app.get("/")
async def index(request: Request):
    try:
        data = await _fetch_cowhide_json()
        item = data.get("item", {})

        current_price = int(item.get("current", {}).get("price", 0) or 0)
        today_price_field = str(item.get("today", {}).get("price", "0"))
        item["today_percentage"] = _format_today_percentage(
            current_price, today_price_field
        )

        return templates.TemplateResponse(
            "index.html", {"request": request, "item": item}
        )
    except httpx.HTTPError as exc:
        return JSONResponse(
            status_code=502,
            content={"error": "failed_to_fetch_cowhide", "detail": str(exc)},
        )


@app.get("/raw")
async def get_cowhide_raw():
    try:
        data = await _fetch_cowhide_json()
        return JSONResponse(content=data)
    except httpx.HTTPError as exc:
        return JSONResponse(
            status_code=502,
            content={"error": "failed_to_fetch_cowhide", "detail": str(exc)},
        )
