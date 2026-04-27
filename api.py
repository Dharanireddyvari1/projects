from fastapi import FastAPI, HTTPException, Query, Response

from lens_client import LensFlowError, fetch_exact_match_html


app = FastAPI(title="Google Lens Exact Match API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/google-lens")
def google_lens(imageUrl: str = Query(..., min_length=8)) -> Response:
    try:
        html = fetch_exact_match_html(imageUrl)
    except LensFlowError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unexpected Lens flow failure") from exc

    return Response(content=html, media_type="text/html; charset=utf-8")
