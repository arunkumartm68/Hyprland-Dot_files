import pytest

from hyprtheme.core.templating import Template, TemplateError, render

DATA = {
    "colors": {"primary": "#00E5FF", "surface": "#11151D"},
    "effects": {"opacity": 0.85, "blur": 12, "glass": True, "radius": 14, "pos": "top"},
    "stops": ["#ff0000", "#00ff00"],
}


def test_variables_and_filters():
    out = render(
        "{{ colors.primary | hypr(0.8) }}|{{ colors.surface | rgba(effects.opacity) }}|{{ effects.radius | mul(0.5) | int }}", DATA
    )
    assert out == "rgba(00e5ffcc)|rgba(17, 21, 29, 0.85)|7"


def test_conditionals():
    tpl = "{% if effects.glass and effects.blur > 0 %}glass{% elif effects.blur == 0 %}flat{% else %}x{% endif %}"
    assert render(tpl, DATA) == "glass"
    assert render(tpl, {"effects": {"glass": False, "blur": 0}}) == "flat"
    assert render(tpl, {"effects": {"glass": False, "blur": 3}}) == "x"
    assert render('{% if effects.pos == "top" %}T{% endif %}', DATA) == "T"
    assert render("{% if not effects.glass %}no{% else %}yes{% endif %}", DATA) == "yes"


def test_loops_and_comments():
    out = render("{% for s in stops %}{{ s | hypr }}{% if not loop.last %} {% endif %}{% endfor %}{# gone #}", DATA)
    assert out == "rgba(ff0000ff) rgba(00ff00ff)"


def test_standalone_tags_do_not_leave_blank_lines():
    out = render("a\n{% if effects.glass %}\n  b\n{% endif %}\nc\n", DATA)
    assert out == "a\n  b\nc\n"


def test_errors():
    with pytest.raises(TemplateError):
        render("{{ colors.nope }}", DATA)
    with pytest.raises(TemplateError):
        render("{{ colors.primary | bogus }}", DATA)
    with pytest.raises(TemplateError):
        Template("{% if x %}unterminated")
    with pytest.raises(TemplateError):
        render("{{ colors.primary | hypr('x') }}", DATA)


def test_misc_filters():
    assert render("{{ effects.glass | yesno }} {{ effects.glass | truefalse }} {{ effects.opacity | pct }}", DATA) == "yes true 85"
    assert render("{{ colors.primary | readable }}", DATA) == "#0B0D12"
    assert render("{{ colors.primary | mix(colors.surface, 0.5) }}", DATA) == "#087D8E"
    assert render("{{ missing | default('d') }}", {"missing": ""}) == "d"
    assert render("{{ 3 | add(4) }}/{{ 10 | div(4) }}/{{ 9 | max(10) }}", {}) == "7/2.5/10"
