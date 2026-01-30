from dokuWikiDumper.utils.util import check_int, _is_disallowed_in_robots_txt

def test_check_int():
    assert 1 == check_int(1)
    assert check_int("a") is None
    assert "1" == check_int("1")
    assert 1.1 == check_int(1.1)
    assert None is check_int(None)


def test_robots_txt_full_disallow():
    """Test that a full site disallow (Disallow: /) is correctly detected"""
    robots_txt = """User-agent: ia_archiver
Disallow: /
"""
    assert _is_disallowed_in_robots_txt(robots_txt, 'ia_archiver') == True


def test_robots_txt_path_disallow_not_full():
    """Test that a path disallow (Disallow: /path/) is NOT treated as full site disallow"""
    # This is the bug case from the issue
    robots_txt = """User-agent: *
Disallow: /DI/cours/ImagerieNumerique/tp/
"""
    assert _is_disallowed_in_robots_txt(robots_txt, 'ia_archiver') == False
    assert _is_disallowed_in_robots_txt(robots_txt, 'dokuwikidumper') == False


def test_robots_txt_wildcard_user_agent():
    """Test that wildcard user agent (*) applies to all bots"""
    robots_txt = """User-agent: *
Disallow: /
"""
    assert _is_disallowed_in_robots_txt(robots_txt, 'ia_archiver') == True
    assert _is_disallowed_in_robots_txt(robots_txt, 'dokuwikidumper') == True
    assert _is_disallowed_in_robots_txt(robots_txt, 'googlebot') == True


def test_robots_txt_specific_user_agent():
    """Test that specific user agent rules are respected"""
    robots_txt = """User-agent: googlebot
Disallow: /

User-agent: ia_archiver
Allow: /
"""
    assert _is_disallowed_in_robots_txt(robots_txt, 'googlebot') == True
    assert _is_disallowed_in_robots_txt(robots_txt, 'ia_archiver') == False


def test_robots_txt_multiple_paths():
    """Test multiple specific path disallows don't trigger full disallow"""
    robots_txt = """User-agent: *
Disallow: /admin/
Disallow: /private/
Disallow: /temp/
"""
    assert _is_disallowed_in_robots_txt(robots_txt, 'ia_archiver') == False


def test_robots_txt_case_insensitive():
    """Test that robots.txt parsing is case-insensitive"""
    robots_txt = """User-Agent: IA_Archiver
Disallow: /
"""
    assert _is_disallowed_in_robots_txt(robots_txt, 'ia_archiver') == True
    assert _is_disallowed_in_robots_txt(robots_txt, 'IA_ARCHIVER') == True


def test_robots_txt_no_disallow():
    """Test that no disallow rules means not disallowed"""
    robots_txt = """User-agent: *
Allow: /
"""
    assert _is_disallowed_in_robots_txt(robots_txt, 'ia_archiver') == False


def test_robots_txt_empty():
    """Test empty robots.txt"""
    assert _is_disallowed_in_robots_txt("", 'ia_archiver') == False


def test_robots_txt_with_comments():
    """Test robots.txt with comments"""
    robots_txt = """# This is a comment
User-agent: ia_archiver
Disallow: /
# Another comment
"""
    assert _is_disallowed_in_robots_txt(robots_txt, 'ia_archiver') == True
    
