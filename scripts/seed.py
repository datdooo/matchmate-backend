from sqlalchemy import select

from app.db.base import Base
from app.db.models import VenueModel
from app.db.session import create_session_factory, engine

DEMO_TAG = "DEMO"


# name:str, address:str, district_code:str; ID do DB cấp
VENUES = [
    ("Sân Cầu Giấy", "Số 1 Trần Thái Tông, Cầu Giấy", "CAU_GIAY"),
    ("Sân Đống Đa", "Số 10 Tây Sơn, Đống Đa", "DONG_DA"),
    ("Sân Ba Đình", "Số 5 Liễu Giai, Ba Đình", "BA_DINH"),
    ("Sân Hoàn Kiếm", "Số 20 Lý Thường Kiệt, Hoàn Kiếm", "HOAN_KIEM"),
    ("Sân Hai Bà Trưng", "Số 30 Minh Khai, Hai Bà Trưng", "HAI_BA_TRUNG"),
    ("Sân Thanh Xuân", "Số 15 Nguyễn Trãi, Thanh Xuân", "THANH_XUAN"),
    ("Sân Hà Đông", "Số 8 Quang Trung, Hà Đông", "HA_DONG"),
    ("Sân Long Biên", "Số 12 Nguyễn Văn Cừ, Long Biên", "LONG_BIEN"),
    ("Sân Nam Từ Liêm", "Số 3 Lê Đức Thọ, Nam Từ Liêm", "NAM_TU_LIEM"),
    ("Sân Tây Hồ", "Số 25 Xuân Diệu, Tây Hồ", "TAY_HO"),
]


def seed_venue(db) -> tuple[int, int]:
    added = skipped = 0
    for name, address, district_code in VENUES:
        full_name = f"{name} {DEMO_TAG}"
        exists = db.scalar(select(VenueModel.id).where(VenueModel.name == full_name))

        if exists:
            skipped += 1
            continue
        db.add(
            VenueModel(
                name=full_name,
                address=f"{address} (demo)",
                district_code=district_code,
                is_active=True,
            )
        )
        added += 1

    return added, skipped


def main() -> None:
    try:
        Base.metadata.create_all(engine)
        session_factory = create_session_factory(engine)
        # begin() commit khi thành công, rollback khi lỗi; không cần Session lồng nhau.
        with session_factory.begin() as db:
            added, skipped = seed_venue(db)
        print(f"Seed xong: thêm {added} sân, bỏ qua {skipped} sân đã có.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
