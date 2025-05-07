from dokuWikiDumper.utils.util import check_int

def test_check_int():
    assert 1 == check_int(1)
    assert check_int("a") is None
    assert "1" == check_int("1")
    assert 1.1 == check_int(1.1)
    assert None is check_int(None)
    
