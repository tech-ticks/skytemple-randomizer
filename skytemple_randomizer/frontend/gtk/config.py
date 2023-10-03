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

import sys
from enum import Enum
from functools import partial
from numbers import Number
from typing import List, Dict, cast

import strictyaml
from gi.repository import Gtk, GtkSource
from jsonschema import validate
from range_typed_integers import u8, u16, u32

from skytemple_files.common.ppmdu_config.dungeon_data import Pmd2DungeonDungeon, Pmd2DungeonItem, \
    Pmd2DungeonItemCategory
from skytemple_files.data.md.protocol import Ability
from skytemple_files.dungeon_data.mappa_bin.protocol import MAX_ITEM_ID
from skytemple_randomizer.config import RandomizerConfig, CLASSREF, DungeonSettingsConfig, IntRange, QuizQuestion, \
    QUIZ_QUESTIONS_JSON_SCHEMA
from skytemple_randomizer.frontend.gtk.ui_util import builder_get_assert, builder_get_assert_exist, iter_tree_model
from skytemple_randomizer.lists import MOVES, MONSTERS
from skytemple_randomizer.randomizer.common.items import ALLOWED_ITEM_CATS


def is_int(typ):
    return typ == int or typ == u8 or typ == u16 or typ == u32


class ConfigUIApplier:
    """Applies configuration to the UI widgets."""
    def __init__(
            self,
            builder: Gtk.Builder,
            dungeons: list[Pmd2DungeonDungeon],
            items: list[Pmd2DungeonItem],
            item_cats: dict[int, Pmd2DungeonItemCategory]
    ):
        self.builder = builder
        self.dungeons = dungeons
        self.items = items
        self.item_cats = item_cats

    def apply(self, config: RandomizerConfig):
        builder_get_assert(self.builder, Gtk.ListStore, 'store_tree_dungeons_dungeons').clear()
        builder_get_assert(self.builder, Gtk.ListStore, 'store_tree_monsters_abilities').clear()
        builder_get_assert(self.builder, Gtk.ListStore, 'store_tree_monsters_monsters').clear()
        builder_get_assert(self.builder, Gtk.ListStore, 'store_tree_monsters_moves').clear()
        builder_get_assert(self.builder, Gtk.ListStore, 'store_tree_dungeons_items').clear()
        builder_get_assert(self.builder, Gtk.ListStore, 'store_tree_item_weights').clear()
        builder_get_assert(self.builder, Gtk.ListStore, 'store_tree_monsters_starters').clear()
        self._handle(config)

    def _handle(self, config, field_name=None):
        if isinstance(config, dict) and CLASSREF in config:
            typ = config[CLASSREF]
        else:
            typ = config.__class__
        if typ == list and field_name == 'quiz_questions':
            buffer: GtkSource.Buffer = builder_get_assert(self.builder, GtkSource.View, 'text_quiz_content').get_buffer()
            validate(config, QUIZ_QUESTIONS_JSON_SCHEMA)
            buffer.set_text(strictyaml.as_document(config).as_yaml())
        elif hasattr(typ, '__bases__') and dict in typ.__bases__ and len(typ.__annotations__) > 0:
            for field, field_type in typ.__annotations__.items():
                field_full = field
                if field_name is not None:
                    field_full = field_name + '_' + field
                self._handle(config[field], field_full)
        elif hasattr(typ, '__bases__') and Enum in typ.__bases__:
            self._handle(config.value, field_name)
        elif typ == bool:
            assert field_name, "Field name must be set for primitive"
            w1 = builder_get_assert_exist(self.builder, Gtk.Switch, 'switch_' + field_name)
            w1.set_active(config)
        elif is_int(typ):
            assert field_name, "Field name must be set for primitive"
            w2 = builder_get_assert_exist(self.builder, Gtk.ComboBox, 'cb_' + field_name)
            w2.set_active_id(str(config))
        elif typ == IntRange:
            assert field_name, "Field name must be set for primitive"
            w3 = builder_get_assert_exist(self.builder, Gtk.Scale, 'scale_' + field_name)
            w3.set_value(getattr(config, 'value'))
        elif typ == str:
            assert field_name, "Field name must be set for primitive"
            try:
                w4 = builder_get_assert_exist(self.builder, Gtk.Entry, 'entry_' + field_name)
                w4.set_text(config)
            except ValueError:
                w5 = builder_get_assert_exist(self.builder, Gtk.TextView, 'text_' + field_name)
                w5.get_buffer().set_text(config)
        elif typ == dict and len(config) > 0 and isinstance(next(iter(config.values())), dict):
            # DUNGEON SETTINGS
            w6 = builder_get_assert_exist(self.builder, Gtk.TreeView, 'tree_' + field_name)
            s6 = cast(Gtk.ListStore, w6.get_model())
            for idx, settings in config.items():
                settings6 = cast(DungeonSettingsConfig, settings)
                s6.append([idx, self._get_dungeon_name(idx), settings6['randomize'], settings6['monster_houses'],
                           settings6['randomize_weather'], settings6['unlock'], settings6['enemy_iq']])
        elif typ == dict and len(config) > 0 and isinstance(next(iter(config.values())), Number):
            # ITEM WEIGHTS
            w7 = builder_get_assert_exist(self.builder, Gtk.TreeView, 'tree_' + field_name)
            s7 = cast(Gtk.ListStore, w7.get_model())
            for idx, weight in config.items():
                idx = int(idx)
                if idx in ALLOWED_ITEM_CATS:
                    s7.append([idx, self._get_cat_name(idx), str(weight)])
        elif typ == list and (len(config) < 1 or isinstance(next(iter(config)), int)):
            w8: Gtk.TreeView = builder_get_assert_exist(self.builder, Gtk.TreeView, 'tree_' + field_name)
            s8 = cast(Gtk.ListStore, w8.get_model())
            if field_name == 'pokemon_abilities_enabled':
                for a in Ability:
                    if a.value != 0xFF:
                        s8.append([a.value, a.print_name, a.value in config])
            elif field_name == 'dungeons_items_enabled':
                for item in self.items:
                    if item.id <= MAX_ITEM_ID:
                        s8.append([item.id, item.name, item.id in config])
            elif field_name == 'pokemon_moves_enabled':
                for a_mov, name in MOVES.items():
                    s8.append([a_mov, name, a_mov in config])
            elif field_name == 'pokemon_monsters_enabled':
                for a_mon, name in MONSTERS.items():
                    s8.append([a_mon, name, a_mon in config])
            elif field_name == 'pokemon_starters_enabled':
                for a_itm, name in MONSTERS.items():
                    s8.append([a_itm, name, a_itm in config])
        else:
            raise TypeError(f"Unknown type for {self.__class__.__name__}: {typ}")

    def _get_dungeon_name(self, idx):
        return self.dungeons[idx].name

    def _get_cat_name(self, idx):
        return self.item_cats[idx].name


class ConfigUIReader:
    """Loads configuration from the UI widgets."""
    def __init__(self, builder: Gtk.Builder):
        self.builder = builder

    def read(self) -> RandomizerConfig:
        return self._handle(RandomizerConfig)

    def _handle(self, typ: type, field_name=None):
        if typ == list[QuizQuestion]:
            buffer = builder_get_assert(self.builder, GtkSource.View, 'text_quiz_content').get_buffer()
            yaml_content = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
            yaml_obj = strictyaml.load(yaml_content).data
            validate(yaml_obj, QUIZ_QUESTIONS_JSON_SCHEMA)
            return yaml_obj
        if hasattr(typ, '__bases__') and dict in typ.__bases__ and len(typ.__annotations__) > 0:
            d = {}
            for field, field_type in typ.__annotations__.items():
                field_full = field
                if field_name is not None:
                    field_full = field_name + '_' + field
                d[field] = self._handle(field_type, field_full)
            return d
        elif hasattr(typ, '__bases__') and Enum in typ.__bases__:
            return typ(self._handle(int, field_name))
        elif typ == bool:
            assert field_name, "Field name must be set for primitive"
            w1 = builder_get_assert_exist(self.builder, Gtk.Switch, 'switch_' + field_name)
            return w1.get_active()
        elif is_int(typ):
            assert field_name, "Field name must be set for primitive"
            w2 = builder_get_assert_exist(self.builder, Gtk.ComboBox, 'cb_' + field_name)
            active = w2.get_active_id()
            if active:
                return int(active)
            return 0
        elif typ == IntRange:
            assert field_name, "Field name must be set for primitive"
            w3 = builder_get_assert_exist(self.builder, Gtk.Scale, 'scale_' + field_name)
            return typ(int(w3.get_value()))
        elif typ == str:
            assert field_name, "Field name must be set for primitive"
            try:
                w4 = builder_get_assert_exist(self.builder, Gtk.Entry, 'entry_' + field_name)
                return w4.get_text()
            except ValueError:
                w5 = builder_get_assert_exist(self.builder, Gtk.TextView, 'text_' + field_name)
                buffer5 = w5.get_buffer()
                return buffer5.get_text(buffer5.get_start_iter(), buffer5.get_end_iter(), False)
        elif typ == dict[int, DungeonSettingsConfig]:
            w6 = builder_get_assert_exist(self.builder, Gtk.TreeView, 'tree_' + field_name)
            s6 = cast(Gtk.ListStore, w6.get_model())
            d = {}
            for idx, name, randomize, monster_houses, randomize_weather, unlock, enemy_iq in iter_tree_model(s6):
                d[idx] = {'randomize': randomize, 'monster_houses': monster_houses,
                          'randomize_weather': randomize_weather, 'unlock': unlock, 'enemy_iq': enemy_iq}
            return d
        elif typ == dict[int, Number]:
            w7 = builder_get_assert_exist(self.builder, Gtk.TreeView, 'tree_' + field_name)
            s7 = cast(Gtk.ListStore, w7.get_model())
            d = {}
            for idx, name, weight in iter_tree_model(s7):
                d[idx] = float(weight)
            return d
        elif typ.__name__.lower() == "list" and is_int(typ.__args__[0]):  # type: ignore
            w8 = builder_get_assert_exist(self.builder, Gtk.TreeView, 'tree_' + field_name)
            s8 = cast(Gtk.ListStore, w8.get_model())
            dd: list[int] = []
            for idx, name, use in iter_tree_model(s8):
                if use:
                    dd.append(idx)
            return dd
        else:
            raise TypeError(f"Unknown type for {self.__name__}: {typ}")  # type: ignore


class ConfigDocApplier:
    """Connects the help buttons with the text of the *Doc classes."""
    def __init__(self, window, builder: Gtk.Builder):
        self.window = window
        self.builder = builder

    def apply(self):
        return self._handle(type(None), RandomizerConfig)

    def _handle(self, parent_typ: type, typ: type, field_name=None, field_name_short=None):
        if hasattr(typ, '__bases__') and dict in typ.__bases__ and len(typ.__annotations__) > 0:
            for field, field_type in typ.__annotations__.items():
                field_full = field
                if field_name is not None:
                    field_full = field_name + '_' + field
                self._handle(typ, field_type, field_full, field)
        if hasattr(parent_typ, '__name__'):
            current_module = sys.modules['skytemple_randomizer.config']
            if parent_typ.__name__ + 'Doc' in current_module.__dict__:
                cls = current_module.__dict__[parent_typ.__name__ + 'Doc']
                if field_name_short in cls.__dict__:
                    help_name = 'help_' + field_name
                    help_btn = self.builder.get_object(help_name)
                    if not help_btn:
                        raise ValueError(f"Help button {help_name} not found.")
                    help_btn.connect('clicked', partial(
                        self.show_help, '\n'.join([line.strip() for line in cls.__dict__[field_name_short].splitlines()])
                    ))

    def show_help(self, info, *args):
        md = Gtk.MessageDialog(parent=self.window,
                               destroy_with_parent=True,
                               message_type=Gtk.MessageType.INFO,
                               buttons=Gtk.ButtonsType.OK,
                               text=info)
        md.run()
        md.destroy()
