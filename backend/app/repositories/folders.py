from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import NewsItem, TopicFolder
from app.schemas import TopicFolderResponse


def list_folders_with_counts(db: Session) -> list[TopicFolderResponse]:
    folders = db.scalars(select(TopicFolder).order_by(TopicFolder.name)).all()
    counts = dict(
        db.execute(
            select(NewsItem.folder_id, func.count())
            .where(NewsItem.folder_id.is_not(None))
            .group_by(NewsItem.folder_id)
        ).all()
    )
    return [
        TopicFolderResponse(
            id=folder.id,
            name=folder.name,
            item_count=counts.get(folder.id, 0),
            created_at=folder.created_at,
        )
        for folder in folders
    ]


def get_folder(db: Session, folder_id: int) -> TopicFolder | None:
    return db.get(TopicFolder, folder_id)
