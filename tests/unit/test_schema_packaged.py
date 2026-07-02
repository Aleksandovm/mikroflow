from mikroflow.db import load_schema_sql


def test_schema_sql_is_packaged_and_loadable():
    sql = load_schema_sql()
    assert "CREATE TABLE IF NOT EXISTS flows_raw" in sql
    assert "ensure_partition_window" in sql
