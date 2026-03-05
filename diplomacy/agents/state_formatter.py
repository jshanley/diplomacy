# ==============================================================================
# Copyright (C) 2019 - Philip Paquette
#
#  This program is free software: you can redistribute it and/or modify it under
#  the terms of the GNU Affero General Public License as published by the Free
#  Software Foundation, either version 3 of the License, or (at your option) any
#  later version.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT
#  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
#  FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
#  details.
#
#  You should have received a copy of the GNU Affero General Public License along
#  with this program.  If not, see <https://www.gnu.org/licenses/>.
# ==============================================================================
"""Serialize Diplomacy game state into structured text for LLM prompts."""


def format_game_state(game, power_name):
    """Format the current game state as structured text for an LLM.

    Includes: phase info, board state (all powers' units and centers),
    the agent's possible orders, and recent messages.

    :param game: Current game state.
    :param power_name: The power the agent is playing.
    :type game: diplomacy.engine.game.Game
    :type power_name: str
    :return: Structured text representation.
    :rtype: str
    """
    phase = game.get_current_phase()
    all_units = game.get_units()
    all_centers = game.get_centers()
    orderable_locs = game.get_orderable_locations(power_name)
    possible_orders = game.get_all_possible_orders()
    power_names = sorted(game.get_map_power_names())

    lines = []
    lines.append('# Diplomacy — Phase %s' % phase)
    lines.append('# You are: %s' % power_name)
    lines.append('')

    # Board state
    lines.append('## Board State')
    for pn in power_names:
        units = all_units.get(pn, [])
        centers = all_centers.get(pn, [])
        tag = ' (YOU)' if pn == power_name else ''
        lines.append('%s%s: %d centers, %d units' % (pn, tag, len(centers), len(units)))
        lines.append('  Units: %s' % (', '.join(sorted(units)) if units else '(none)'))
        lines.append('  Centers: %s' % (', '.join(sorted(centers)) if centers else '(none)'))
    lines.append('')

    # Possible orders for this power
    lines.append('## Your Possible Orders')
    if not orderable_locs:
        lines.append('(no orderable locations)')
    for loc in sorted(orderable_locs):
        loc_orders = possible_orders.get(loc, [])
        if loc_orders:
            lines.append('%s:' % loc)
            for order in sorted(loc_orders):
                lines.append('  - %s' % order)
    lines.append('')

    # Messages from the current phase
    _append_messages(lines, game.messages, power_name, 'Recent Messages This Phase')

    # Message history from last 2 phases
    history = game.message_history
    if history:
        phase_keys = sorted(history.keys())[-2:]
        past_messages = {}
        for pk in phase_keys:
            for ts, msg in history[pk].items():
                past_messages[ts] = msg
        if past_messages:
            _append_messages(lines, past_messages, power_name,
                             'Message History (Last 2 Phases)', show_phase=True)

    return '\n'.join(lines)


def format_message_prompt(game, power_name):
    """Format a prompt for generating diplomatic messages during Talk phases.

    Includes: phase info, board summary, recent messages received,
    and instructions on who can be messaged.

    :param game: Current game state.
    :param power_name: The power the agent is playing.
    :type game: diplomacy.engine.game.Game
    :type power_name: str
    :return: Structured text prompt for message generation.
    :rtype: str
    """
    phase = game.get_current_phase()
    all_units = game.get_units()
    all_centers = game.get_centers()
    power_names = sorted(game.get_map_power_names())

    lines = []
    lines.append('# Diplomacy — Talk Phase %s' % phase)
    lines.append('# You are: %s' % power_name)
    lines.append('')

    # Compact board summary
    lines.append('## Board Summary')
    for pn in power_names:
        units = all_units.get(pn, [])
        centers = all_centers.get(pn, [])
        tag = ' (YOU)' if pn == power_name else ''
        lines.append('%s%s: %d centers, %d units' % (pn, tag, len(centers), len(units)))
    lines.append('')

    # Who you can message
    other_powers = [pn for pn in power_names if pn != power_name]
    lines.append('## You Can Send Messages To')
    for pn in other_powers:
        lines.append('  - %s' % pn)
    lines.append('  - GLOBAL (all powers)')
    lines.append('')

    # Recent messages
    _append_messages(lines, game.messages, power_name, 'Messages This Phase')

    # Message history
    history = game.message_history
    if history:
        phase_keys = sorted(history.keys())[-3:]
        past_messages = {}
        for pk in phase_keys:
            for ts, msg in history[pk].items():
                past_messages[ts] = msg
        if past_messages:
            _append_messages(lines, past_messages, power_name,
                             'Recent Message History', show_phase=True)

    return '\n'.join(lines)


def _append_messages(lines, messages, power_name, header, show_phase=False):
    """Append formatted messages to lines list.

    Only includes messages visible to the given power (sent to them,
    sent by them, or sent to GLOBAL).
    """
    if not messages:
        return
    relevant = []
    for ts in sorted(messages.keys()):
        msg = messages[ts]
        if (msg.sender == power_name or
                msg.recipient == power_name or
                msg.recipient == 'GLOBAL'):
            relevant.append(msg)
    if not relevant:
        return
    lines.append('## %s' % header)
    for msg in relevant:
        phase_prefix = '[%s] ' % msg.phase if show_phase else ''
        lines.append('%s%s -> %s: %s' % (phase_prefix, msg.sender, msg.recipient, msg.message))
    lines.append('')
