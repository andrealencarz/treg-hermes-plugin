from prospector.hermes_plugin import register


def test_registration_is_side_effect_free(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    class Context:
        def __init__(self):
            self.tools = []
            self.cli = []

        def register_tool(self, **kwargs):
            self.tools.append(kwargs["name"])

        def register_cli_command(self, **kwargs):
            self.cli.append(kwargs["name"])

    context = Context()
    register(context)
    assert len(context.tools) == 10
    assert context.cli == ["prospector"]
    assert list(tmp_path.iterdir()) == []
