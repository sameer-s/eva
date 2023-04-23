from pytest import fixture
from eva.catalog.sql_config import SQLConfig
from eva.server.command_handler import execute_query_fetch_all

# This is a global fixture that will be used by all tests
@fixture(autouse=True)
def wrap_test_in_transaction():
    execute_query_fetch_all("BEGIN TRANSACTION")
    yield
    execute_query_fetch_all("END TRANSACTION")