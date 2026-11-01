from learning_rag.metrics.p_n import p50


def test_empty_is_none():
    assert p50([]) is None


def test_odd_count_uses_the_middle_value():
    assert p50([30.0, 10.0, 20.0]) == 20.0


def test_even_count_averages_the_middle_values():
    assert p50([1.0, 3.0, 5.0, 7.0]) == 4.0
