from sqlalchemy import select

from app.db.base import Base
from app.db.models import VenueModel
from app.db.session import create_session_factory, engine

DEMO_TAG = "DEMO"


# id:int, name:str, address:str, district_code:str
VENNUES = [
    (1, "Sân Cầu Giấy", "Số 1 Trần Thái Tông, Cầu Giấy", "CAU_GIAY"),
    (2, "Sân Đống Đa", "Số 10 Tây Sơn, Đống Đa", "DONG_DA"),
    (3, "Sân Ba Đình", "Số 5 Liễu Giai, Ba Đình", "BA_DINH"),
    (4, "Sân Hoàn Kiếm", "Số 20 Lý Thường Kiệt, Hoàn Kiếm", "HOAN_KIEM"),
    (5, "Sân Hai Bà Trưng", "Số 30 Minh Khai, Hai Bà Trưng", "HAI_BA_TRUNG"),
    (6, "Sân Thanh Xuân", "Số 15 Nguyễn Trãi, Thanh Xuân", "THANH_XUAN"),
    (7, "Sân Hà Đông", "Số 8 Quang Trung, Hà Đông", "HA_DONG"),
    (8, "Sân Long Biên", "Số 12 Nguyễn Văn Cừ, Long Biên", "LONG_BIEN"),
    (9, "Sân Nam Từ Liêm", "Số 3 Lê Đức Thọ, Nam Từ Liêm", "NAM_TU_LIEM"),
    (10, "Sân Tây Hồ", "Số 25 Xuân Diệu, Tây Hồ", "TAY_HO"),
]


def seed_venue(db) -> tuple[int, int]:
    added = skipped = 0
    for id, name, address, district_code in VENNUES:
        full_name = f"{name} {DEMO_TAG}"
        exists = db.scalar(select(VenueModel.id).where(VenueModel.name == full_name))

        if exists:
            skipped += 1
            continue
        else:
            db.add(
                VenueModel(
                    id=id,
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
