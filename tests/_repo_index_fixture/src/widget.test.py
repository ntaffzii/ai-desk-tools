from widget import normalize_widget_name


def test_normalize_widget_name():
    assert normalize_widget_name(" Demo ") == "demo"
