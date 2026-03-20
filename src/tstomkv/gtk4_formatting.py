"""Formatting and data-shaping helpers for the GTK4 filtered titles UI."""


def _display_title(title):
    return str(title) if title else "<No title>"


def _sort_key(value):
    return _display_title(value).lower()


def _sorted_recordings_for_title(recordings):
    return sorted(recordings, key=lambda rec: rec.get("filename") or "")


def _build_title_rows(titles):
    """Build sorted rows for the title list UI and text rendering."""
    rows = []
    for title in sorted(titles.keys(), key=_sort_key):
        recordings = _sorted_recordings_for_title(titles[title])
        rows.append(
            {
                "title": title,
                "display": _display_title(title),
                "count": len(recordings),
                "recordings": recordings,
            }
        )
    return rows


def _format_title_details(title, recordings):
    """Return details text for one selected title."""
    heading = _display_title(title)
    lines = [f"{heading}", f"Recordings: {len(recordings)}", ""]

    for rec in recordings:
        filename = rec.get("filename") or "<unknown>"
        subtitle = rec.get("subtitle")
        channel = rec.get("channelname")
        episode = rec.get("episode")
        season = rec.get("season")

        if subtitle:
            lines.append(f"- {subtitle}")
        else:
            lines.append("- <No subtitle>")

        lines.append(f"  file: {filename}")
        if channel:
            lines.append(f"  channel: {channel}")
        if season or episode:
            lines.append(f"  episode: S{season or '?'} E{episode or '?'}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _format_filtered_titles(recs, titles):
    """Create readable text output from filteredTitles()."""
    rows = _build_title_rows(titles)
    lines = [
        f"Transport Stream recordings: {len(recs)}",
        f"Unique titles: {len(rows)}",
        "",
    ]

    if not rows:
        lines.append("No recordings returned by filteredTitles().")
        return "\n".join(lines) + "\n"

    for row in rows:
        lines.append(f"{row['display']} ({row['count']})")
        for rec in row["recordings"]:
            filename = rec.get("filename") or "<unknown>"
            subtitle = rec.get("subtitle")
            if subtitle:
                lines.append(f"  - {subtitle}: {filename}")
            else:
                lines.append(f"  - {filename}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _format_conversion_list(selected_titles_data):
    """Format selected titles into a conversion list."""
    if not selected_titles_data:
        return "No titles selected for conversion.\n"

    lines = ["Conversion List", "=" * 40, ""]
    for row_data in selected_titles_data:
        title = row_data["display"]
        count = row_data["count"]
        recordings = row_data["recordings"]

        lines.append(f"{title} ({count} recording{'' if count == 1 else 's'})")
        for rec in recordings:
            filename = rec.get("filename") or "<unknown>"
            lines.append(f"  {filename}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
