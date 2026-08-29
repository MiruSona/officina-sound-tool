"""결과 표를 찍는다. 한글은 두 칸으로 세서 칸이 안 어긋나게 한다."""


def print_table(rows):
    widths = [max(width(row[i]) for row in rows) for i in range(len(rows[0]))]
    for index, row in enumerate(rows):
        cells = [cell + " " * (widths[i] - width(cell)) for i, cell in enumerate(row)]
        print("| " + " | ".join(cells) + " |")
        if index == 0:
            print("| " + " | ".join("-" * w for w in widths) + " |")


def width(text):
    """East Asian Wide 는 두 칸."""
    return sum(2 if ord(ch) > 0x2E80 else 1 for ch in text)
