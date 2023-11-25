#  Copyright 2020-2023 Capypara and the SkyTemple Contributors
#
#  This file is part of SkyTemple.
#
#  SkyTemple is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SkyTemple is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SkyTemple.  If not, see <https://www.gnu.org/licenses/>.
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import cast, Callable

from skytemple_randomizer.config import RandomizerConfig
from skytemple_randomizer.frontend.gtk.path import MAIN_PATH

from gi.repository import Gtk, Adw

from skytemple_randomizer.frontend.gtk.widgets import (
    RandomizationSettingsWidget,
    HelpPopover,
)


@dataclass
class SubpageStackEntry:
    child: RandomizationSettingsWidget
    name: str
    title: str
    icon_name: str


@Gtk.Template(filename=os.path.join(MAIN_PATH, "base_dialog_settings.ui"))
class BaseSettingsDialog(Adw.Window):
    __gtype_name__ = "StBaseSettingsDialog"

    header_bar = cast(Adw.HeaderBar, Gtk.Template.Child())
    toolbar_view = cast(Adw.ToolbarView, Gtk.Template.Child())
    content = cast(Adw.Bin, Gtk.Template.Child())
    search_bar = cast(Gtk.SearchBar, Gtk.Template.Child())
    search_entry = cast(Gtk.SearchEntry, Gtk.Template.Child())
    placeholder_toggle = cast(Adw.Bin, Gtk.Template.Child())
    button_search = cast(Gtk.ToggleButton, Gtk.Template.Child())
    action_bar: Gtk.ActionBar | None
    _children: list[RandomizationSettingsWidget]
    _getter: Callable[[], bool] | None
    _setter: Callable[[bool], None] | None

    def __init__(
        self,
        *args,
        content: RandomizationSettingsWidget | tuple[SubpageStackEntry, ...],
        getter: Callable[[], bool] | None = None,
        setter: Callable[[bool], None] | None = None,
        help_callback: Callable[[], str] | None = None,
        search_callback: Callable[[Gtk.SearchEntry], None] | None = None,
        end_button_factory: Callable[[], Gtk.Widget] | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.action_bar = None
        if isinstance(content, tuple):
            self._children = []
            # Make a ViewStack with ViewStack pages and add a view switcher to the title bar
            stack = Adw.ViewStack(vexpand=True)
            for entry in content:
                stack.add_titled_with_icon(
                    cast(Gtk.Widget, entry.child),
                    entry.name,
                    entry.title,
                    entry.icon_name,
                )
                self._children.append(entry.child)
            view_switcher = Adw.ViewSwitcher(
                stack=stack, policy=Adw.ViewSwitcherPolicy.WIDE
            )
            self.header_bar.set_title_widget(view_switcher)
        else:
            self.content.set_child(cast(Gtk.Widget, content))
            self._children = [content]

        if help_callback is not None or end_button_factory is not None:
            self.action_bar = Gtk.ActionBar()
            self.toolbar_view.add_bottom_bar(self.action_bar)

        if help_callback is not None:
            assert self.action_bar is not None
            help_button = Gtk.MenuButton(
                icon_name="skytemple-help-about-symbolic",
                popover=HelpPopover(label=help_callback()),
            )
            self.action_bar.pack_start(help_button)

        if search_callback is not None:
            self.search_entry.connect("search-changed", search_callback)
        else:
            self.search_bar.hide()
            self.button_search.hide()

        if end_button_factory is not None:
            assert self.action_bar is not None
            self.action_bar.pack_end(end_button_factory())

        self._getter = getter
        self._setter = setter

    @Gtk.Template.Callback()
    def on_realize(self, *args):
        if sys.platform.startswith("darwin"):
            self.header_bar.set_decoration_layout("close:")

        close_esc = Gtk.Shortcut(
            trigger=Gtk.ShortcutTrigger.parse_string("Escape|<Control>w"),
            action=Gtk.NamedAction(action_name="window.close"),
        )
        self.add_shortcut(close_esc)

    @Gtk.Template.Callback()
    def on_button_search_clicked(self, *args):
        self.search_bar.set_search_mode(not self.search_bar.get_search_mode())

    @Gtk.Template.Callback()
    def on_search_bar_notify_search_mode_enabled(self, *args):
        self.button_search.set_active(self.search_bar.get_search_mode())

    def populate_settings(self, config: RandomizerConfig):
        for child in self._children:
            child.populate_settings(config)

        if self._getter is not None and self._setter is not None:
            # Add a switch to toggle the feature on and off
            def switch_notify_active(*args):
                self._setter(switch.get_active())  # type: ignore
                active = switch.get_active()
                self.content.set_sensitive(active)
                if self.action_bar is not None:
                    self.action_bar.set_sensitive(active)

            switch = Gtk.Switch(active=self._getter())
            active = switch.get_active()
            self.content.set_sensitive(active)
            if self.action_bar is not None:
                self.action_bar.set_sensitive(active)
            switch.connect("notify::active", switch_notify_active)
            self.placeholder_toggle.set_child(switch)
