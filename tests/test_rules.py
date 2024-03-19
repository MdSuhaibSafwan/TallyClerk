from datetime import date

from tallyclerk import Config, Severity, check, document_from_dict


def ids(report):
    return {f.rule_id for f in report.findings}


def test_clean_shipment_has_no_discrepancies(clean_docs):
    report = check(clean_docs)
    assert report.verdict == "CLEAN"
    assert [f.rule_id for f in report.findings] == ["TC007"]  # advisory only


def test_discrepant_shipment_catches_every_planted_error(discrepant_docs):
    report = check(discrepant_docs)
    assert report.verdict == "DISCREPANT"
    assert ids(report) == {
        "TC002", "TC003", "TC007", "TC101", "TC103", "TC104", "TC105", "TC106",
        "TC109", "TC110", "TC112", "TC203", "TC204", "TC205",
    }


def test_findings_sorted_by_severity(discrepant_docs):
    severities = [f.severity for f in check(discrepant_docs).findings]
    assert severities == sorted(severities, reverse=True)


def test_select_and_ignore_by_prefix(discrepant_docs):
    only_lc = check(discrepant_docs, select=["TC2"])
    assert ids(only_lc) == {"TC203", "TC204", "TC205"}
    no_lc = check(discrepant_docs, ignore=["TC2", "TC007"])
    assert not any(i.startswith("TC2") for i in ids(no_lc)) and "TC007" not in ids(no_lc)


def doc(doc_type, **fields):
    return document_from_dict({"doc_type": doc_type, **fields})


def test_bl_shipper_may_differ_from_seller():
    # UCP 600 Art. 14(k): a third-party shipper on the B/L is acceptable.
    docs = [doc("invoice", seller="Meghna Knit Composite Ltd"),
            doc("bl", shipper="Chattogram Freight Consolidators Ltd")]
    assert "TC101" not in ids(check(docs))


def test_to_order_bl_compares_notify_party():
    docs = [doc("invoice", buyer="Nordwind Textil GmbH"),
            doc("bl", consignee="TO ORDER OF HANSEATIC HANDELSBANK AG",
                notify_party="Nordwind Textil GmbH")]
    assert "TC102" not in ids(check(docs))
    docs[1] = doc("bl", consignee="TO ORDER", notify_party="Someone Else Trading BV")
    assert "TC102" in ids(check(docs))


def test_weight_tolerance_is_configurable():
    docs = [doc("pl", gross_weight="1000 KG"), doc("bl", gross_weight="1004 KG")]
    assert "TC103" not in ids(check(docs, Config(weight_tolerance_pct=0.5)))
    assert "TC103" in ids(check(docs, Config(weight_tolerance_pct=0.1)))


def test_unit_conversion_before_comparison():
    docs = [doc("pl", gross_weight="1,000 KG"), doc("bl", gross_weight="2,204.6 LBS")]
    assert "TC103" not in ids(check(docs))


def test_retired_incoterm_is_explained():
    report = check([doc("invoice", incoterm="DAT Hamburg")])
    [finding] = [f for f in report.findings if f.rule_id == "TC005"]
    assert "DPU" in finding.message


def test_freight_terms_follow_incoterm():
    docs = [doc("invoice", incoterm="CIF Hamburg"), doc("bl", freight_terms="FREIGHT COLLECT")]
    assert "TC112" in ids(check(docs))
    docs[1] = doc("bl", freight_terms="FREIGHT PREPAID")
    assert "TC112" not in ids(check(docs))


def test_generic_lc_port_is_not_compared():
    docs = [doc("bl", port_of_loading="Chattogram"),
            doc("lc", port_of_loading="ANY PORT IN BANGLADESH")]
    assert "TC107" not in ids(check(docs))


def test_unreadable_value_is_reported():
    report = check([doc("pl", gross_weight="about a truckload")])
    assert [f.rule_id for f in report.findings] == ["TC001"]
    assert report.findings[0].severity == Severity.WARNING


def test_lc_tolerance_allows_overdraw():
    lc = doc("lc", credit_amount="USD 100,000", amount_tolerance="10/10")
    assert "TC203" not in ids(check([doc("invoice", total="USD 109,000"), lc]))
    assert "TC203" in ids(check([doc("invoice", total="USD 111,000"), lc]))


def test_presentation_date_from_config():
    docs = [doc("bl", shipped_on_board="2026-03-01"), doc("lc", expiry_date="2026-06-30")]
    assert "TC205" not in ids(check(docs))  # no presentation date known
    late = Config(presented_on=date(2026, 3, 25))
    assert "TC205" in ids(check(docs, late))


def test_invoice_must_be_issued_by_beneficiary():
    docs = [doc("invoice", seller="Other Exporter Ltd", buyer="Nordwind Textil GmbH"),
            doc("lc", beneficiary="Meghna Knit Composite Ltd", applicant="Nordwind Textil GmbH")]
    findings = [f for f in check(docs).findings if f.rule_id == "TC201"]
    assert len(findings) == 1 and "beneficiary" in findings[0].message
