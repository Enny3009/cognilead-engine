import pytest
from app.services.scoring_service import ScoringService


def test_job_title_evaluation() -> None:
    service = ScoringService(None)  # type: ignore[arg-type]

    vp_score, cat = service.evaluate_job_title("VP of Engineering")
    assert vp_score == 25
    assert cat == "senior_executive"

    mgr_score, cat = service.evaluate_job_title("Regional Sales Manager")
    assert mgr_score == 15
    assert cat == "management"

    dev_score, cat = service.evaluate_job_title("Software Developer")
    assert dev_score == 5


def test_business_email_filter() -> None:
    service = ScoringService(None)  # type: ignore[arg-type]

    assert service.is_business_email("alex@apexmartech.io") is True
    assert service.is_business_email("john.doe@gmail.com") is False
    assert service.is_business_email("mark@yahoo.com") is False