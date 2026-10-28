"""GET /corpus/versions — read-only corpus metadata."""
from fastapi import APIRouter
from sqlalchemy import select, func
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import CorpusDocument, get_db_session

router = APIRouter(tags=["corpus"])


@router.get("/corpus/versions")
async def get_corpus_versions(session: AsyncSession = Depends(get_db_session)):
    swc_count = await session.scalar(
        select(func.count(CorpusDocument.id)).where(CorpusDocument.kind == "swc")
    )
    postmortem_count = await session.scalar(
        select(func.count(CorpusDocument.id)).where(CorpusDocument.kind == "postmortem")
    )
    # Get latest version
    latest = await session.scalar(
        select(CorpusDocument.version).order_by(CorpusDocument.created_at.desc()).limit(1)
    )
    return {
        "current": latest or "none",
        "documents": {
            "swc": swc_count or 0,
            "postmortem": postmortem_count or 0,
        },
    }
