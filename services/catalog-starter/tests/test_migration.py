from sqlalchemy import text


async def test_migrations_give_every_column_the_model_reads(stand):
    async with stand.app.state.engine.connect() as connection:
        rows = await connection.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = 'products'")
        )
        have = {row[0] for row in rows}
    for want in ("id", "title", "price", "stock", "reserved", "version"):
        assert want in have, f"после миграций в таблице products нет колонки {want}"
