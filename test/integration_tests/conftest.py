from pytest import fixture
from eva.catalog.catalog_manager import CatalogManager
from eva.storage.transaction_manager import TransactionManager

# This is a global fixture that will be used by all tests
@fixture(autouse=True)
def wrap_test_in_transaction(request):
    if 'notparallel' in request.keywords:
        yield
    else:
        TransactionManager().begin_transaction()
        yield
        TransactionManager().rollback_transaction()