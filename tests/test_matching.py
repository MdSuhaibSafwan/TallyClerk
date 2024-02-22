import pytest

from tallyclerk.matching import is_to_order, name_similarity, name_tokens
from tallyclerk.reference import normalize_incoterm, normalize_port


@pytest.mark.parametrize("a, b", [
    ("Nordwind Textil GmbH", "NORDWIND TEXTIL G.M.B.H."),
    ("Nordwind Textil GmbH", "Nordwind Textil GmbH, Speicherstadt 7, Hamburg"),
    ("Meghna Knit Composite Ltd.", "MEGHNA KNIT COMPOSITE LIMITED"),
    ("Anadolu Tekstil San. ve Tic. A.Ş.", "ANADOLU TEKSTIL SANAYI VE TICARET AS"),
])
def test_same_company_variants_match(a, b):
    assert name_similarity(a, b) >= 0.85


@pytest.mark.parametrize("a, b", [
    ("Meghna Knit Composite Ltd.", "Meghna Knitwear Industries Ltd."),
    ("Nordwind Textil GmbH", "Nordstern Mode GmbH"),
])
def test_different_companies_do_not_match(a, b):
    assert name_similarity(a, b) < 0.85


def test_name_tokens_strip_legal_form():
    assert name_tokens("ACME Trading Co., Ltd.") == ["acme", "trading"]


def test_to_order():
    assert is_to_order("TO THE ORDER OF HANSEATIC HANDELSBANK AG")
    assert is_to_order("to order")
    assert not is_to_order("Nordwind Textil GmbH")


@pytest.mark.parametrize("raw", ["Chittagong", "CHATTOGRAM, BANGLADESH", "Port of Chittagong", "BDCGP"])
def test_port_aliases(raw):
    assert normalize_port(raw) == "BDCGP"


def test_unknown_port_falls_back_to_clean_name():
    assert normalize_port("Port of Pointe-Noire") == normalize_port("POINTE NOIRE")


def test_normalize_incoterm():
    assert normalize_incoterm("FOB Chittagong, Incoterms 2020") == ("FOB", "Chittagong")
    assert normalize_incoterm("cif") == ("CIF", None)
    assert normalize_incoterm("C&F Hamburg") == ("C&F", "Hamburg")
