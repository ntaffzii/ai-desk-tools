class WidgetStore:
    def create_widget(self, name: str) -> dict:
        return {"name": name}


def normalize_widget_name(value: str) -> str:
    return value.strip().lower()
