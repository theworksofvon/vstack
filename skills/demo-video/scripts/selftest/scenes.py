"""The self-test scenes: 1 card, then a click, a dialog, typing and a fast part."""

from kit import card, scene

card("00", kicker="Self-test", title="Does the <em>full flow</em> work?", seconds=2.5)


@scene("01", "Confirm an order")
def confirm(d):
    d.goto("PAGE_URL")
    name = d.page.locator("#name")
    d.ring(name, "Type here", hold=1.0, zoom=1.5)
    d.click(name)
    d.type("Copper")
    add = d.page.locator("#add")
    d.click(add)
    dialog = d.page.get_by_role("dialog")
    d.focus(dialog, zoom=1.3)
    d.wait(0.8)
    d.click(d.page.locator("#yes"))
    d.wide()
    d.wait(3.0)
    # Dialogs that open and close at high speed: the edit must drop the strobe.
    with d.fast_forward("5 more orders · 10× speed"):
        for _ in range(5):
            d.click(add, after=0.2)
            d.click(d.page.locator("#yes"), after=0.2)
    assert d.page.locator("#count").inner_text() == "6"
    d.ring(d.page.locator("#count"), "6 orders", hold=1.0, zoom=1.4)
