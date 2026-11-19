"""Pure playlist sizing helpers."""


def balanced_parts(track_ids: list[str], maximum: int = 100) -> list[list[str]]:
    """Split tracks into the fewest balanced, contiguous parts within maximum."""
    if maximum <= 0:
        raise ValueError("maximum must be positive")
    if not track_ids:
        return []

    part_count = (len(track_ids) + maximum - 1) // maximum
    size, extra = divmod(len(track_ids), part_count)
    parts = []
    start = 0
    for index in range(part_count):
        end = start + size + (index < extra)
        parts.append(track_ids[start:end])
        start = end
    return parts
