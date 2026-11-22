from sqlalchemy import event

from app.db.models import VenueModel


def test_venue_filters_count_and_pagination_are_applied_before_page(
    client, db_session_factory, game_data
):
    with db_session_factory.begin() as db:
        db.add_all(
            [
                VenueModel(id=10, name="Active A", address="A", district_code="CAU_GIAY"),
                VenueModel(
                    id=11, name="Inactive", address="A", district_code="CAU_GIAY", is_active=False
                ),
                VenueModel(id=12, name="Other", address="B", district_code="DONG_DA"),
                VenueModel(id=13, name="Active B", address="A", district_code="CAU_GIAY"),
            ]
        )
    response = client.get("/venues", params={"district_code": "CAU_GIAY", "limit": 1, "offset": 1})
    assert response.status_code == 200
    page = response.json()
    assert page["total"] == 3
    assert [v["id"] for v in page["items"]] == [10]


def test_discovery_public_projection_and_inactive_history(
    client, db_engine, db_session_factory, game_data, auth_headers
):
    queries = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            queries.append(statement)

    event.listen(db_engine, "before_cursor_execute", capture)
    try:
        response = client.get("/sessions", params={"limit": 1, "offset": 1})
    finally:
        event.remove(db_engine, "before_cursor_execute", capture)
    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert [g["id"] for g in response.json()["items"]] == [game_data["second"]]
    assert queries and all("password_hash" not in q and "email" not in q for q in queries)
    with db_session_factory.begin() as db:
        db.get(VenueModel, game_data["venue"]).is_active = False
    assert client.get("/sessions").json()["total"] == 0
    assert client.get("/venues").json()["total"] == 0
    host = auth_headers(game_data["host"])
    detail = client.get(f"/sessions/{game_data['first']}", headers=host)
    assert detail.status_code == 200
    assert detail.json()["venue"]["is_active"] is False
    assert client.get("/sessions?host_me=true", headers=host).json()["total"] == 2
