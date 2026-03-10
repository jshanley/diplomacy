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
"""Parse LLM text responses into validated Diplomacy orders and messages."""
import re


def parse_orders(llm_response, possible_orders, orderable_locs):
    """Extract valid order strings from an LLM response.

    Scans each line of the response, strips common formatting (bullets,
    numbering, backticks), and checks for exact matches against the set
    of possible orders for the agent's orderable locations.

    :param llm_response: Raw text response from the LLM.
    :param possible_orders: Dict mapping location -> set of valid order strings.
    :param orderable_locs: List of locations the agent can order.
    :type llm_response: str
    :type possible_orders: dict
    :type orderable_locs: list
    :return: List of valid order strings (at most one per location).
    :rtype: list[str]
    """
    # Build lookup: order_string -> location
    order_to_loc = {}
    for loc in orderable_locs:
        for order in possible_orders.get(loc, []):
            order_to_loc[order] = loc

    found = []
    used_locs = set()

    for line in llm_response.split('\n'):
        cleaned = _clean_line(line)
        if not cleaned:
            continue

        # Try exact match first
        if cleaned in order_to_loc:
            loc = order_to_loc[cleaned]
            if loc not in used_locs:
                found.append(cleaned)
                used_locs.add(loc)
            continue

        # Try case-insensitive match
        cleaned_upper = cleaned.upper()
        for order, loc in order_to_loc.items():
            if loc not in used_locs and order.upper() == cleaned_upper:
                found.append(order)
                used_locs.add(loc)
                break

    return found


def parse_messages(llm_response, power_names):
    """Extract diplomatic messages from an LLM response.

    Expects lines in the format ``RECIPIENT: message body`` where RECIPIENT
    is a valid power name or ``GLOBAL``.

    :param llm_response: Raw text response from the LLM.
    :param power_names: List of valid power names in the game.
    :type llm_response: str
    :type power_names: list[str]
    :return: List of (recipient, body) tuples.
    :rtype: list[tuple[str, str]]
    """
    valid_recipients = set(power_names) | {'GLOBAL'}
    messages = []

    for line in llm_response.split('\n'):
        cleaned = _clean_line(line)
        if not cleaned:
            continue
        # Match "RECIPIENT: body" or "RECIPIENT -> body"
        match = re.match(r'^([A-Z]+)\s*(?::|->|→)\s*(.+)$', cleaned)
        if match:
            recipient = match.group(1).upper()
            body = match.group(2).strip()
            if recipient in valid_recipients and body:
                messages.append((recipient, body))

    return messages


def _clean_line(line):
    """Strip common LLM formatting from a line.

    Removes: leading/trailing whitespace, bullet markers (-, *, +),
    numbered list prefixes (1., 2.), and backticks.
    """
    s = line.strip()
    # Remove backticks
    s = s.replace('`', '')
    # Remove bullet markers
    s = re.sub(r'^[-*+]\s+', '', s)
    # Remove numbered list prefixes (e.g. "1. ", "12. ")
    s = re.sub(r'^\d+\.\s+', '', s)
    return s.strip()
