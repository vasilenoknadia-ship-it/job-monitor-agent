import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from normalizer.normalizer import normalize_company_name, normalize_job_title


def test_company_name_strips_legal_suffix():
    assert normalize_company_name("UAB SANIFINAS") == "sanifinas"
    assert normalize_company_name("Vinted, UAB") == "vinted,"
    assert normalize_company_name("BURGA Ltd.") == "burga"


def test_company_name_normalizes_ampersand_and_case():
    assert normalize_company_name("Groupe SEB") == "groupe seb"
    assert normalize_company_name("Stanley Black & Decker") == "stanley black and decker"


def test_job_title_normalizes_ecommerce_variants():
    assert normalize_job_title("E-commerce Manager") == "ecommerce manager"
    assert normalize_job_title("Ecommerce Manager") == "ecommerce manager"
    assert normalize_job_title("E commerce Manager") == "ecommerce manager"


def test_job_title_normalizes_hyphens_and_case():
    assert normalize_job_title("Senior Amazon Team-Lead") == "senior amazon team lead"
