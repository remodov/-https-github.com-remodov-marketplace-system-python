from sqlalchemy import text


async def test_migrations_give_every_column_the_model_reads(stand):
    async with stand.app.state.engine.connect() as connection:
        rows = await connection.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = 'products'")
        )
        have = {row[0] for row in rows}
    for want in ("id", "title", "price", "stock", "reserved", "version"):
        assert want in have, f"после миграций в таблице products нет колонки {want}"


async def test_trigram_index_is_in_place(stand):
    async with stand.app.state.engine.connect() as connection:
        rows = await connection.execute(
            text("SELECT indexname FROM pg_indexes WHERE tablename = 'products' AND indexdef LIKE '%gin_trgm_ops%'")
        )
        names = [row[0] for row in rows]
    assert len(names) == 1, "триграммного gin-индекса по title нет"
