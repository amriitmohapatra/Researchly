"""The reading summary (2026-10-14; Codex review #5): what was read and
what was set aside, in counts and plain words. Synthetic text only."""

from researchly_service.schemas import AnalyzeResponse

TEXT = ("We fitted the model in R. The estimates were stable across the "
        "regions, the weekly counts were complete, and the residuals showed "
        "no pattern over time or between the age groups we compared.\n\n"
        "fit <- glm(cases ~ week, family = poisson)\n"
        "summary(fit)\n\n"
        "Os resultados mostram que a vacinação reduziu a transmissão entre "
        "os grupos mais vulneráveis e que o efeito foi maior nas crianças.\n")


def test_the_reply_says_what_was_set_aside(client):
    r = client.post("/v1/analyze", json={"content": TEXT})
    body = AnalyzeResponse.model_validate(r.json())
    got = {s.kind: s.count for s in body.reading.set_aside}
    assert got == {"code": 2, "other_language": 1}
    assert body.reading.words_checked > 0
    assert any("not in English" in w for w in body.warnings)


def test_plain_prose_sets_nothing_aside(client):
    r = client.post("/v1/analyze",
                    json={"content": "The results were clear and robust.\n"})
    assert r.json()["reading"]["set_aside"] == []
