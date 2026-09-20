"""The one-line "reason" on the dashboard is cut at a word, never in the middle of one."""

from app.echo.service import short_reason

LONG = (
    "45F with sudden chest pain radiating to the left arm on exertion for 2 days, worsening. "
    "Abnormal ECG at the urgent care clinic yesterday."
)


def test_first_sentence_is_used():
    assert short_reason(LONG) == (
        "45F with sudden chest pain radiating to the left arm on exertion for 2 days, worsening"
    )


def test_long_sentences_are_cut_at_a_word_with_an_ellipsis():
    text = "Persistent " + "headache and dizziness " * 12
    out = short_reason(text, 60)
    assert out.endswith("…") and len(out) <= 61
    assert out[:-1].split()[-1] in {"headache", "and", "dizziness", "Persistent"}  # a whole word


def test_short_text_is_unchanged_apart_from_whitespace():
    assert (
        short_reason("  Knee pain,\nsuspected meniscal tear. ")
        == "Knee pain, suspected meniscal tear"
    )


def test_reasons_saved_by_the_old_hard_cut_are_healed_when_read():
    from types import SimpleNamespace as NS

    from app.echo.service import EchoService, _Bundle

    reason = LONG[:90]  # what the old code saved: cut mid-word
    b = _Bundle(
        ref=None,
        patient=None,
        pmeta=None,
        meta=NS(
            reason=reason,
            details=LONG,
            specialty="Cardiology",
            subspecialty="",
            preferred_distance_miles=25,
        ),
        run=None,
    )
    assert EchoService._describe(b)[0].endswith("worsening")
    kept = NS(
        reason="Chest pain",
        details=LONG,
        specialty="",
        subspecialty="",
        preferred_distance_miles=25,
    )
    assert (
        EchoService._describe(_Bundle(ref=None, patient=None, pmeta=None, meta=kept, run=None))[0]
        == "Chest pain"
    )
