from policies.policy_engine import CitationPolicy


def test_citation_policy_accepts_returned_source() -> None:
    check = CitationPolicy().evaluate(
        "Restart the client and retry [vpn-access.md].",
        {"vpn-access.md"},
    )

    assert check.passed


def test_citation_policy_rejects_missing_citation() -> None:
    check = CitationPolicy().evaluate("Restart the client and retry.", {"vpn-access.md"})

    assert not check.passed


def test_citation_policy_rejects_unapproved_citation() -> None:
    check = CitationPolicy().evaluate(
        "Restart the client [unapproved.md].",
        {"vpn-access.md"},
    )

    assert not check.passed
