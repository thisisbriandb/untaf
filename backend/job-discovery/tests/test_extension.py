from app.api.extension import Answer, Question, _sanitize, split_name, url_key


def test_url_key_ignores_tracking_and_apply_suffix():
    a = url_key("https://www.welcometothejungle.com/fr/companies/acme/jobs/dev_paris?utm_source=x#top")
    b = url_key("https://welcometothejungle.com/fr/companies/acme/jobs/dev_paris/apply")
    assert a == b == "welcometothejungle.com/fr/companies/acme/jobs/dev_paris"


def test_url_key_rejects_garbage():
    assert url_key("pas une adresse") == ""


def test_split_name():
    assert split_name("Briand Bataillon") == ("Briand", "Bataillon")
    assert split_name("Jean Pierre De La Tour") == ("Jean", "Pierre De La Tour")
    assert split_name("") == ("", "")


def test_sanitize_keeps_known_options_only_and_fills_missing():
    qs = [
        Question(id="a", label="Permis B ?", kind="radio", options=["Oui", "Non"]),
        Question(id="b", label="Pays", kind="select", options=["France", "Belgique"]),
        Question(id="c", label="Motivation", kind="textarea"),
    ]
    raw = [Answer(id="a", value="oui"), Answer(id="b", value="Mars"), Answer(id="zz", value="x")]
    out = {a.id: a.value for a in _sanitize(qs, raw)}
    assert out == {"a": "Oui", "b": None, "c": None}
