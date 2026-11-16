WIDTH = 68


def title(text):
    print()
    print("=" * WIDTH)
    print(text.center(WIDTH))
    print("=" * WIDTH)


def stage(no, label, detail):
    print()
    print("-" * WIDTH)
    print("  STAGE {}  |  {}".format(no, label))
    print("  {}".format(detail))
    print("-" * WIDTH)


def step(text):
    print("     * " + text)


def sub(text):
    print("         - " + text)


def ok(text):
    print("     [OK] " + text)


def warn(text):
    print("     [!] " + text)


def fail(text):
    print("     [X]  " + text)


def hr():
    print("     " + "-" * (WIDTH - 4))


def summary(rows):
    """rows: list of (source, found, inserted)."""
    print()
    print("=" * WIDTH)
    print("  RINGKASAN SCRAPING".center(WIDTH))
    print("=" * WIDTH)
    print("  {:<16}{:>15}{:>15}".format("SUMBER", "DITEMUKAN", "DIMASUKKAN"))
    print("  " + "-" * (WIDTH - 2))
    tot_found = 0
    tot_ins = 0
    for src, found, ins in rows:
        print("  {:<16}{:>15}{:>15}".format(src, found, ins))
        tot_found += found
        tot_ins += ins
    print("  " + "-" * (WIDTH - 2))
    print("  {:<16}{:>15}{:>15}".format("TOTAL", tot_found, tot_ins))
    print("=" * WIDTH)
    print()